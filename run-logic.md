# Backend Implementation Instructions for Runs Execution

## Overview
Implement an API endpoint to execute test runs by replaying proven_steps from test cases sequentially. Update Firestore in real-time so the frontend can display live progress.

## API Endpoint

**POST** `/api/runs/execute`

**Request Body:**
```json
{
  "run_id": "string",
  "tenant_id": "string"
}
```

**Response:**
```json
{
  "success": true,
  "run_id": "string",
  "message": "Run execution started"
}
```

---

## Implementation Flow

### 1. Fetch Run Data
```javascript
// Get run document from Firestore
const run = await db.collection('runs').doc(run_id).get();
const runData = run.data();

// Update status to "running"
await db.collection('runs').doc(run_id).update({
  status: 'running',
  started_at: new Date().toISOString()
});
```

### 2. Execute Test Cases Sequentially
```javascript
for (let i = 0; i < runData.test_case_ids.length; i++) {
  const testCaseId = runData.test_case_ids[i];
  
  // Update current test case index
  await db.collection('runs').doc(run_id).update({
    current_test_case_index: i
  });
  
  // Execute this test case
  await executeTestCase(run_id, testCaseId, i);
}
```

### 3. Execute Single Test Case
```javascript
async function executeTestCase(runId, testCaseId, index) {
  // 1. Fetch test case to get proven_steps
  const testCase = await db.collection('test_cases').doc(testCaseId).get();
  const provenSteps = testCase.data().proven_steps || [];
  
  // 2. Update result status to "running"
  await db.collection('runs').doc(runId).update({
    [`results.${testCaseId}.status`]: 'running',
    [`results.${testCaseId}.started_at`]: new Date().toISOString(),
    [`results.${testCaseId}.total_steps`]: provenSteps.length
  });
  
  // 3. Create E2B sandbox for this test case
  const sandbox = await createSandbox();
  const vncUrl = sandbox.vnc_url;
  
  // 4. Update with VNC URL
  await db.collection('runs').doc(runId).update({
    [`results.${testCaseId}.vnc_url`]: vncUrl
  });
  
  try {
    // 5. Execute proven_steps sequentially
    for (let stepIndex = 0; stepIndex < provenSteps.length; stepIndex++) {
      const step = provenSteps[stepIndex];
      
      // Update current step
      await db.collection('runs').doc(runId).update({
        [`results.${testCaseId}.current_step`]: stepIndex + 1
      });
      
      // Execute the step using e2b_browser tool
      await executeStep(sandbox, step);
      
      // Small delay between steps
      await sleep(500);
    }
    
    // 6. Mark test case as passed
    await db.collection('runs').doc(runId).update({
      [`results.${testCaseId}.status`]: 'passed',
      [`results.${testCaseId}.completed_at`]: new Date().toISOString()
    });
    
  } catch (error) {
    // 7. Mark test case as failed
    await db.collection('runs').doc(runId).update({
      [`results.${testCaseId}.status`]: 'failed',
      [`results.${testCaseId}.error`]: error.message,
      [`results.${testCaseId}.completed_at`]: new Date().toISOString()
    });
  } finally {
    // 8. Close sandbox
    await sandbox.close();
  }
}
```

### 4. Execute Proven Step
```javascript
async function executeStep(sandbox, step) {
 
}
```

### 5. Complete Run
```javascript
// After all test cases executed
const updatedRun = await db.collection('runs').doc(run_id).get();
const allResults = Object.values(updatedRun.data().results);
const allPassed = allResults.every(r => r.status === 'passed');
const anyFailed = allResults.some(r => r.status === 'failed');

await db.collection('runs').doc(run_id).update({
  status: anyFailed ? 'failed' : 'completed',
  completed_at: new Date().toISOString()
});
```

---

## Firestore Document Structure

### runs/{runId}
```javascript
{
  id: "run123",
  tenant_id: "tenant456",
  project_id: "project789",
  name: "Regression Run #1",
  test_case_ids: ["tc1", "tc2", "tc3"],
  status: "running", // pending | running | completed | failed
  created_at: "2025-10-23T00:00:00Z",
  created_by: "user123",
  started_at: "2025-10-23T00:01:00Z",
  current_test_case_index: 1,
  results: {
    "tc1": {
      test_case_id: "tc1",
      status: "passed",
      vnc_url: "https://...",
      started_at: "2025-10-23T00:01:00Z",
      completed_at: "2025-10-23T00:02:00Z",
      current_step: 8,
      total_steps: 8
    },
    "tc2": {
      test_case_id: "tc2",
      status: "running",
      vnc_url: "https://...",
      started_at: "2025-10-23T00:02:00Z",
      current_step: 3,
      total_steps: 5
    },
    "tc3": {
      test_case_id: "tc3",
      status: "pending",
      current_step: 0,
      total_steps: 0
    }
  }
}
```

---

## Proven Steps Structure (from test_cases)

Each test case has a `proven_steps` array:

```javascript
proven_steps: [
  {
    step_number: 1,
    tool_name: "e2b_browser",
    arguments: {
      action: "navigate_to",
      url: "https://example.com"
    }
  },
  {
    step_number: 2,
    tool_name: "e2b_browser",
    arguments: {
      action: "click_element",
      index: 0
    }
  },
  {
    step_number: 3,
    tool_name: "e2b_browser",
    arguments: {
      action: "input_text",
      index: 0,
      text: "test@example.com"
    }
  },
  {
    step_number: 4,
    tool_name: "e2b_browser",
    arguments: {
      action: "wait",
      seconds: 2
    }
  },
  {
    step_number: 5,
    tool_name: "e2b_browser",
    arguments: {
      action: "assert_url_contains",
      expected_text: "/dashboard",
      assertion_description: "Successfully logged in"
    }
  },
  {
    step_number: 6,
    tool_name: "e2b_browser",
    arguments: {
      action: "assert_element_visible",
      search_text: "Welcome",
      assertion_description: "Welcome message is visible"
    }
  }
]
```

---

## Action Types Reference

| Action | Arguments | Description |
|--------|-----------|-------------|
| `navigate_to` | `url` | Navigate browser to URL |
| `click_element` | `index` | Click element at index |
| `input_text` | `index`, `text` | Input text into element |
| `wait` | `seconds` | Wait for N seconds |
| `assert_url_contains` | `expected_text`, `assertion_description` | Assert URL contains text |
| `assert_element_visible` | `search_text`, `assertion_description` | Assert element is visible |

---

## Key Requirements

1. **Execute sequentially** - one test case at a time, one step at a time
2. **Update Firestore in real-time** - after each step completion
3. **Use nested field updates** - `results.${testCaseId}.status` syntax to update specific test case
4. **Create one sandbox per test case** - don't reuse sandboxes between test cases
5. **Handle errors gracefully** - mark test case as failed, continue to next
6. **Clean up resources** - close sandboxes after each test case
7. **Provide VNC URL** - frontend displays live browser view

---

## Error Handling

- **If a step fails** → mark test case as "failed", store error message, continue to next test case
- **If sandbox creation fails** → mark test case as "failed", continue to next test case  
- **If all test cases complete** → mark run as "completed"
- **If any test case fails** → mark run status as "failed" (but execution completes)

---

## Frontend Integration

Frontend uses Firestore real-time listener to get live updates:

```javascript
import { doc, onSnapshot } from "firebase/firestore";

const runRef = doc(db, 'runs', runId);
const unsubscribe = onSnapshot(runRef, (snapshot) => {
  const runData = snapshot.data();
  // UI automatically updates with:
  // - Overall progress
  // - Current test case status
  // - Step-by-step progress
  // - VNC URL for active test case
});
```

**No polling needed** - Firestore pushes updates to frontend instantly.

---

## Testing

1. Create a test case with proven_steps in the UI
2. Create a run and add that test case
3. Call the API endpoint
4. Watch the frontend update in real-time as:
   - Run status changes to "running"
   - Each test case executes
   - Steps complete one by one
   - VNC shows live browser
   - Final status shows passed/failed

---

---

## Future Enhancements

- Parallel execution (multiple test cases at once)
- Screenshot capture on failures
- Detailed logs for each step
- Retry failed test cases
- Schedule runs (cron jobs)
- Email notifications on completion

