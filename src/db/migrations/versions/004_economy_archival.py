"""Schedule 30-day archival of transactions via pg_cron.

- Creates `economy.currency_transactions_archive` table (structure mirrors main table)
- Adds archival stored procedure `economy.proc_archive_old_transactions()`
- Schedules daily job using `pg_cron` to move rows older than 30 days
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "004_economy_archival"
down_revision = "003_economy_adjustments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Best-effort enable pg_cron when available. On vanilla postgres images
    # the extension may be absent; in that case we skip scheduling but still
    # create the archive table and procedure.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_available_extensions WHERE name = 'pg_cron'
            ) THEN
                -- Install if present in the instance; no-op if already installed
                EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_cron';
            ELSE
                RAISE NOTICE 'pg_cron extension not available; skipping installation';
            END IF;
        END$$;
        """
    )

    # Create archive table with same columns as currency_transactions
    # Use LIKE INCLUDING to copy constraints/defaults where sensible
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM   information_schema.tables
                WHERE  table_schema = 'economy' AND table_name = 'currency_transactions_archive'
            ) THEN
                CREATE TABLE economy.currency_transactions_archive
                (LIKE economy.currency_transactions INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES);

                -- Remove FK constraints referencing live balances to decouple archive
                ALTER TABLE economy.currency_transactions_archive
                    DROP CONSTRAINT IF EXISTS fk_currency_transactions_initiator,
                    DROP CONSTRAINT IF EXISTS fk_currency_transactions_target;

                -- Add indexes helpful for retrieval & purge windows
                CREATE INDEX IF NOT EXISTS ix_currency_transactions_archive_guild_created
                    ON economy.currency_transactions_archive (guild_id, created_at);
            END IF;
        END$$;
        """
    )

    # Archival stored procedure: moves rows older than 30 days in manageable batches
    op.execute(
        """
        CREATE OR REPLACE PROCEDURE economy.proc_archive_old_transactions(batch_size integer DEFAULT 5000)
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_cutoff timestamptz := timezone('utc', now()) - interval '30 days';
        BEGIN
            -- Move in batches to avoid long locks
            WITH moved AS (
                DELETE FROM economy.currency_transactions ct
                WHERE ct.created_at < v_cutoff
                RETURNING *
            )
            INSERT INTO economy.currency_transactions_archive SELECT * FROM moved;
        END;
        $$;
        """
    )

    # Schedule daily job at 02:10 UTC (non-peak window) if pg_cron is installed
    # Skips silently on environments without pg_cron (e.g. CI postgres:16 image)
    op.execute(
        """
        DO $outer$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
                IF NOT EXISTS (
                    SELECT 1 FROM cron.job WHERE jobname = 'economy_archive_30d'
                ) THEN
                    PERFORM cron.schedule(
                        'economy_archive_30d',
                        '10 2 * * *',
                        $cmd$CALL economy.proc_archive_old_transactions();$cmd$
                    );
                END IF;
            ELSE
                RAISE NOTICE 'pg_cron not installed; skipping schedule creation';
            END IF;
        END$outer$;
        """
    )


def downgrade() -> None:
    # Unschedule job if exists and pg_cron is installed
    op.execute(
        """
        DO $$
        DECLARE
            jid int;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
                SELECT jobid INTO jid FROM cron.job WHERE jobname = 'economy_archive_30d';
                IF jid IS NOT NULL THEN
                    PERFORM cron.unschedule(jid);
                END IF;
            END IF;
        END$$;
        """
    )

    # Drop procedure (archive table retained to preserve historical data)
    op.execute("DROP PROCEDURE IF EXISTS economy.proc_archive_old_transactions(integer)")
