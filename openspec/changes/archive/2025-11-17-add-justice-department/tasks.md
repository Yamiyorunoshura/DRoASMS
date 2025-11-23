## 1. Database and Core Services

- [x] 1.1 Create migration for `governance.suspects` table
- [x] 1.2 Run database migration
- [x] 1.3 Verify table structure
- [x] 1.4 Create `JusticeService` class
- [x] 1.5 Implement `get_suspects` method
- [x] 1.6 Implement `charge_suspect` method
- [x] 1.7 Implement `is_member_charged` method
- [x] 1.8 Add error handling to `JusticeService`
- [x] 1.9 Update `HomelandSecurityService` release logic
- [x] 1.10 Add prosecution status check to release flow
- [x] 1.11 Update error messages in `HomelandSecurityService`

## 2. Economic Commands Update

- [x] 2.1 Update `/transfer` command to recognize Justice Department role
- [x] 2.2 Update role mapping logic in transfer service
- [x] 2.3 Add Justice Department to valid target list
- [x] 2.4 Update help text for transfer command
- [x] 2.5 Update `/adjust` command to recognize Justice Department role
- [x] 2.6 Update role checking logic in adjustment service
- [x] 2.7 Add permission checks for Justice Department adjustments
- [x] 2.8 Update audit logging for Justice Department operations

## 3. State Council Panel UI

- [x] 3.1 Add Justice Department tab to State Council panel
- [x] 3.2 Design suspect list view with pagination
- [x] 3.3 Add "Charge" button to suspect list
- [x] 3.4 Add "Drop Charges" button for charged suspects
- [x] 3.5 Implement suspect details view
- [x] 3.6 Add button callback handlers
- [x] 3.7 Add confirmation dialogs for prosecution actions
- [x] 3.8 Implement modal for entering charge reason
- [x] 3.9 Add success/failure feedback for operations

## 4. Testing

- [x] 4.1 Write unit tests for `JusticeService`
- [x] 4.2 Test suspect list retrieval with pagination
- [x] 4.3 Test charge suspect functionality
- [x] 4.4 Test check prosecution status functionality
- [x] 4.5 Test error scenarios in `JusticeService`
- [x] 4.6 Write integration test for prosecution flow
- [x] 4.7 Test Homeland Security release blocking logic
- [x] 4.8 Test transfer command with Justice Department
- [x] 4.9 Test adjust command with Justice Department
- [x] 4.10 Test concurrent operations
- [x] 4.11 Test Discord command interactions
- [x] 4.12 Test UI button functionality
- [x] 4.13 Test multi-user scenarios
- [x] 4.14 Perform load testing with large suspect lists

## 5. Documentation and Deployment

- [x] 5.1 Update user manual with Justice Department features
- [x] 5.2 Update admin guide for new commands
- [x] 5.3 Document API changes in JusticeService
- [x] 5.4 Add operation examples to documentation
- [x] 5.5 Create deployment script
- [x] 5.6 Prepare rollback plan
- [x] 5.7 Update monitoring metrics
- [x] 5.8 Verify production configuration
