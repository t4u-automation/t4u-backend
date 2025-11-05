"""Shared Test Cases Utility - Resolve and execute shared test case dependencies"""

from typing import Dict, List, Set, Tuple, Optional
from app.firestore import firestore_client
from app.utils.logger import logger


class CircularDependencyError(Exception):
    """Raised when circular dependency is detected in shared test cases"""
    pass


class SharedTestCaseNotFoundError(Exception):
    """Raised when a shared test case is not found"""
    pass


async def get_test_case_data(test_case_id: str, tenant_id: str) -> Optional[Dict]:
    """
    Fetch test case data from Firestore
    
    Args:
        test_case_id: Test case ID
        tenant_id: Tenant ID (for validation)
        
    Returns:
        Test case data dict or None if not found
    """
    if not firestore_client.enabled:
        return None
    
    try:
        doc_ref = firestore_client.db.collection("test_cases").document(test_case_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
            
        return doc.to_dict()
    except Exception as e:
        logger.error(f"Error fetching test case {test_case_id}: {e}")
        return None


async def resolve_shared_test_cases(
    test_case_id: str,
    tenant_id: str,
    visited: Optional[Set[str]] = None,
    path: Optional[List[str]] = None
) -> Dict[str, List[str]]:
    """
    Recursively resolve all shared test cases (before/after) for a test case.
    
    This function builds a complete execution chain by traversing the dependency tree.
    It detects circular dependencies and preserves execution order.
    
    Args:
        test_case_id: The test case ID to resolve
        tenant_id: Tenant ID for validation
        visited: Set of visited test case IDs (for cycle detection)
        path: Current path in the dependency tree (for error messages)
        
    Returns:
        Dict with flattened arrays:
        {
            "before": ["tc_1", "tc_2", ...],  # All before test cases, ordered
            "after": ["tc_5", "tc_6", ...]     # All after test cases, ordered
        }
        
    Raises:
        CircularDependencyError: If a circular dependency is detected
        SharedTestCaseNotFoundError: If a shared test case doesn't exist
    """
    if visited is None:
        visited = set()
    if path is None:
        path = []
    
    # Check for circular dependency
    if test_case_id in visited:
        cycle_path = " -> ".join(path + [test_case_id])
        raise CircularDependencyError(
            f"Circular dependency detected: {cycle_path}"
        )
    
    # Mark as visited
    visited.add(test_case_id)
    path.append(test_case_id)
    
    # Fetch test case data
    test_case_data = await get_test_case_data(test_case_id, tenant_id)
    
    if not test_case_data:
        raise SharedTestCaseNotFoundError(
            f"Test case not found: {test_case_id}"
        )
    
    # Get shared test cases for this test case
    shared_test_cases = test_case_data.get("shared_test_cases", {})
    before_list = shared_test_cases.get("before", [])
    after_list = shared_test_cases.get("after", [])
    
    # Result arrays (will be flattened)
    all_before = []
    all_after = []
    
    # Recursively resolve each "before" test case
    for before_tc_id in before_list:
        # Recursively resolve this before test case
        resolved = await resolve_shared_test_cases(
            before_tc_id,
            tenant_id,
            visited.copy(),  # Use copy to allow siblings to share dependencies
            path.copy()
        )
        
        # Add its before test cases first
        all_before.extend(resolved["before"])
        
        # Then add the test case itself
        all_before.append(before_tc_id)
        
        # Note: We don't add "after" test cases from before dependencies
        # They'll be handled by their own execution
    
    # Recursively resolve each "after" test case
    for after_tc_id in after_list:
        # Add the test case itself first
        all_after.append(after_tc_id)
        
        # Then recursively resolve this after test case
        resolved = await resolve_shared_test_cases(
            after_tc_id,
            tenant_id,
            visited.copy(),
            path.copy()
        )
        
        # Add its after test cases last
        all_after.extend(resolved["after"])
        
        # Note: We don't add "before" test cases from after dependencies
        # They'll be handled by their own execution
    
    return {
        "before": all_before,
        "after": all_after
    }


async def get_full_execution_chain(
    test_case_id: str,
    tenant_id: str
) -> Dict[str, List[Dict]]:
    """
    Get the complete execution chain with test case data for a test case.
    
    This is the main entry point for getting all test cases that need to be executed.
    
    Args:
        test_case_id: The main test case ID
        tenant_id: Tenant ID
        
    Returns:
        Dict with execution chain:
        {
            "before": [
                {"test_case_id": "tc_1", "proven_steps": [...], ...},
                {"test_case_id": "tc_2", "proven_steps": [...], ...}
            ],
            "main": {"test_case_id": "tc_main", "proven_steps": [...], ...},
            "after": [
                {"test_case_id": "tc_5", "proven_steps": [...], ...},
                {"test_case_id": "tc_6", "proven_steps": [...], ...}
            ]
        }
        
    Raises:
        CircularDependencyError: If circular dependency detected
        SharedTestCaseNotFoundError: If any test case not found
    """
    try:
        # Resolve shared test cases
        resolved = await resolve_shared_test_cases(test_case_id, tenant_id)
        
        # Get main test case data
        main_test_case = await get_test_case_data(test_case_id, tenant_id)
        if not main_test_case:
            raise SharedTestCaseNotFoundError(f"Main test case not found: {test_case_id}")
        
        # Fetch all before test case data
        before_test_cases = []
        for tc_id in resolved["before"]:
            tc_data = await get_test_case_data(tc_id, tenant_id)
            if not tc_data:
                raise SharedTestCaseNotFoundError(f"Before test case not found: {tc_id}")
            before_test_cases.append(tc_data)
        
        # Fetch all after test case data
        after_test_cases = []
        for tc_id in resolved["after"]:
            tc_data = await get_test_case_data(tc_id, tenant_id)
            if not tc_data:
                raise SharedTestCaseNotFoundError(f"After test case not found: {tc_id}")
            after_test_cases.append(tc_data)
        
        logger.info(f"Execution chain for {test_case_id}:")
        logger.info(f"  Before: {[tc['test_case_id'] for tc in before_test_cases]}")
        logger.info(f"  Main: {test_case_id}")
        logger.info(f"  After: {[tc['test_case_id'] for tc in after_test_cases]}")
        
        return {
            "before": before_test_cases,
            "main": main_test_case,
            "after": after_test_cases
        }
        
    except CircularDependencyError as e:
        logger.error(f"Circular dependency error: {e}")
        raise
    except SharedTestCaseNotFoundError as e:
        logger.error(f"Shared test case not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Error getting execution chain: {e}")
        raise


def calculate_total_steps(execution_chain: Dict[str, any]) -> Tuple[int, Dict[str, Tuple[int, int]]]:
    """
    Calculate total steps and step ranges for an execution chain.
    
    Args:
        execution_chain: Result from get_full_execution_chain()
        
    Returns:
        Tuple of (total_steps, step_ranges) where step_ranges is:
        {
            "tc_1": (0, 5),      # Steps 0-4 (5 steps)
            "tc_2": (5, 8),      # Steps 5-7 (3 steps)
            "tc_main": (8, 15),  # Steps 8-14 (7 steps)
            "tc_3": (15, 20),    # Steps 15-19 (5 steps)
        }
    """
    total = 0
    step_ranges = {}
    
    # Before test cases
    for tc in execution_chain["before"]:
        tc_id = tc["test_case_id"]
        steps = len(tc.get("proven_steps", []))
        step_ranges[tc_id] = (total, total + steps)
        total += steps
    
    # Main test case
    main_tc_id = execution_chain["main"]["test_case_id"]
    main_steps = len(execution_chain["main"].get("proven_steps", []))
    step_ranges[main_tc_id] = (total, total + main_steps)
    total += main_steps
    
    # After test cases
    for tc in execution_chain["after"]:
        tc_id = tc["test_case_id"]
        steps = len(tc.get("proven_steps", []))
        step_ranges[tc_id] = (total, total + steps)
        total += steps
    
    return total, step_ranges

