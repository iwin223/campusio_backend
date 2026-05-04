"""API Router for Account Hierarchy

Endpoints for:
- Hierarchy creation and management
- Node creation and relationships
- Balance rollup calculations
- Hierarchy tree queries
- Consolidated reporting
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from services.account_hierarchy_service import (
    AccountHierarchyService,
    AccountHierarchyError,
)
from models.finance.account_hierarchy import (
    AccountHierarchyType,
    HierarchyLevel,
)
from dependencies import get_db, get_current_user, get_current_school_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/account-hierarchy", tags=["Account Hierarchy"])


# ==================== Hierarchy Creation ====================

@router.post("/hierarchies", response_model=dict)
async def create_hierarchy(
    hierarchy_name: str = Query(...),
    hierarchy_type: AccountHierarchyType = Query(...),
    description: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new account hierarchy
    
    Defines a new hierarchical structure for GL accounts (e.g., organizational,
    functional, program-based).
    
    Args:
        hierarchy_name: Name of hierarchy (e.g., "Organizational Structure")
        hierarchy_type: Type (ACCOUNT_LEVEL, ORGANIZATIONAL, FUNCTIONAL, etc.)
        description: Optional description
        current_user: Current user
        school_id: School identifier
        session: Database session
        
    Returns:
        Hierarchy ID and confirmation
    """
    try:
        service = AccountHierarchyService(session)
        hierarchy_id = await service.create_hierarchy(
            school_id=school_id,
            hierarchy_name=hierarchy_name,
            hierarchy_type=hierarchy_type,
            description=description,
            created_by=current_user.get("id", "unknown"),
        )
        
        logger.info(
            f"Hierarchy '{hierarchy_name}' created by {current_user.get('id')} "
            f"({hierarchy_type.value})"
        )
        
        return {
            "status": "success",
            "hierarchy_id": hierarchy_id,
            "hierarchy_name": hierarchy_name,
            "hierarchy_type": hierarchy_type.value,
            "next_step": "Create hierarchy nodes",
        }
    except AccountHierarchyError as e:
        logger.warning(f"Error creating hierarchy: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in hierarchy creation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create hierarchy")


# ==================== Node Management ====================

@router.post("/nodes", response_model=dict)
async def create_hierarchy_node(
    hierarchy_id: str = Query(...),
    node_name: str = Query(...),
    node_code: str = Query(...),
    level: HierarchyLevel = Query(...),
    parent_node_id: Optional[str] = Query(None),
    gl_account_id: Optional[str] = Query(None),
    sequence: int = Query(0),
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a hierarchy node
    
    Creates a node in the hierarchy tree. Can be:
    - Detail: Leaf node pointing to GL account
    - Summary: Parent node rolling up children
    - Total: Root node for entire hierarchy
    
    Args:
        hierarchy_id: Parent hierarchy ID
        node_name: Display name
        node_code: Hierarchical code (e.g., "1.1.1" for 3 levels)
        level: Node level (DETAIL, SUMMARY, TOTAL)
        parent_node_id: Parent node (if not root)
        gl_account_id: GL account ID (if detail node)
        sequence: Display order
        school_id: School identifier
        session: Database session
        
    Returns:
        Node ID and confirmation
    """
    try:
        service = AccountHierarchyService(session)
        node_id = await service.create_hierarchy_node(
            school_id=school_id,
            hierarchy_id=hierarchy_id,
            node_name=node_name,
            node_code=node_code,
            level=level,
            parent_node_id=parent_node_id,
            gl_account_id=gl_account_id,
            sequence=sequence,
        )
        
        return {
            "status": "success",
            "node_id": node_id,
            "node_name": node_name,
            "node_code": node_code,
            "level": level.value,
            "parent_node_id": parent_node_id,
        }
    except AccountHierarchyError as e:
        logger.warning(f"Error creating node: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in node creation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create node")


# ==================== Relationship Management ====================

@router.post("/relationships", response_model=dict)
async def add_hierarchy_relationship(
    hierarchy_id: str = Query(...),
    parent_node_id: str = Query(...),
    child_node_id: str = Query(...),
    child_sequence: int = Query(0),
    contribution_percentage: float = Query(100.0),
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Add parent-child relationship in hierarchy
    
    Creates linkage between parent and child nodes. Validates against
    circular references.
    
    Args:
        hierarchy_id: Hierarchy ID
        parent_node_id: Parent node ID
        child_node_id: Child node ID
        child_sequence: Order within parent
        contribution_percentage: % of child that rolls up (default 100%)
        school_id: School identifier
        session: Database session
        
    Returns:
        Relationship confirmation
    """
    try:
        service = AccountHierarchyService(session)
        relationship_id = await service.add_hierarchy_relationship(
            school_id=school_id,
            hierarchy_id=hierarchy_id,
            parent_node_id=parent_node_id,
            child_node_id=child_node_id,
            child_sequence=child_sequence,
            contribution_percentage=contribution_percentage,
        )
        
        return {
            "status": "success",
            "relationship_id": relationship_id,
            "parent_node_id": parent_node_id,
            "child_node_id": child_node_id,
            "child_sequence": child_sequence,
            "contribution_percentage": contribution_percentage,
        }
    except AccountHierarchyError as e:
        logger.warning(f"Error adding relationship: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in relationship creation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to add relationship")


# ==================== Balance Rollup ====================

@router.post("/rollup/{hierarchy_id}", response_model=dict)
async def rollup_all_nodes(
    hierarchy_id: str,
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Calculate rollup balances for all nodes in hierarchy
    
    **CRITICAL OPERATION** - Traverses entire hierarchy tree and calculates
    balance for each node based on GL account balances at detail level.
    
    Args:
        hierarchy_id: Hierarchy ID
        school_id: School identifier
        session: Database session
        
    Returns:
        Rollup completion summary
    """
    try:
        service = AccountHierarchyService(session)
        rollup_data = await service.rollup_all_nodes(school_id, hierarchy_id)
        
        return {
            "status": "success",
            "hierarchy_id": hierarchy_id,
            "nodes_updated": len(rollup_data),
            "rollup_data": rollup_data,
            "timestamp": "now",
        }
    except AccountHierarchyError as e:
        logger.warning(f"Error in rollup: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in rollup process: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to rollup balances")


@router.get("/node-balance/{node_id}", response_model=dict)
async def get_node_balance(
    node_id: str,
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get calculated balance for a hierarchy node
    
    For detail nodes: Returns GL account balance
    For summary nodes: Returns rollup of all descendant detail balances
    
    Args:
        node_id: Node ID
        school_id: School identifier
        session: Database session
        
    Returns:
        Node balance and calculation details
    """
    try:
        service = AccountHierarchyService(session)
        balance = await service.calculate_node_balance(school_id, node_id)
        
        return {
            "node_id": node_id,
            "balance": balance,
            "calculated_at": "now",
        }
    except AccountHierarchyError as e:
        logger.warning(f"Error getting node balance: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating balance: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to calculate balance")


# ==================== Hierarchy Queries ====================

@router.get("/tree/{hierarchy_id}", response_model=dict)
async def get_hierarchy_tree(
    hierarchy_id: str,
    root_node_id: Optional[str] = Query(None),
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get hierarchy tree structure
    
    Returns complete tree structure with all nodes and their balances.
    Optionally start from specific node instead of root.
    
    Args:
        hierarchy_id: Hierarchy ID
        root_node_id: Optional starting node (default: root)
        school_id: School identifier
        session: Database session
        
    Returns:
        Tree structure with node names, codes, and balances
    """
    try:
        service = AccountHierarchyService(session)
        tree = await service.get_hierarchy_tree(
            school_id=school_id,
            hierarchy_id=hierarchy_id,
            root_node_id=root_node_id,
        )
        
        return {
            "hierarchy_id": hierarchy_id,
            "tree": tree,
        }
    except AccountHierarchyError as e:
        logger.warning(f"Error getting tree: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving tree: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get hierarchy tree")


# ==================== Consolidated Reporting ====================

@router.get("/consolidated-report/{hierarchy_id}", response_model=dict)
async def get_consolidated_report(
    hierarchy_id: str,
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get consolidated report by hierarchy level
    
    Returns summary report with:
    - Nodes grouped by level (detail, summary, total)
    - Balance totals at each level
    - Grand total for hierarchy
    
    Useful for:
    - Consolidated financial statements
    - Department-level reporting
    - Program budget vs actual
    - Drill-down analysis
    
    Args:
        hierarchy_id: Hierarchy ID
        school_id: School identifier
        session: Database session
        
    Returns:
        Consolidated report with level-by-level breakdown
    """
    try:
        service = AccountHierarchyService(session)
        report = await service.get_consolidated_report(school_id, hierarchy_id)
        
        return report
    except AccountHierarchyError as e:
        logger.warning(f"Error getting report: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate consolidated report")


# ==================== Export / Reporting ====================

@router.get("/export/{hierarchy_id}", response_model=dict)
async def export_hierarchy_data(
    hierarchy_id: str,
    format: str = Query("json", regex="^(json|csv)$"),
    school_id: str = Depends(get_current_school_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Export hierarchy and balances
    
    Args:
        hierarchy_id: Hierarchy ID to export
        format: Export format (json or csv)
        school_id: School identifier
        session: Database session
        
    Returns:
        Exported data
    """
    try:
        service = AccountHierarchyService(session)
        
        # Get tree and report
        tree = await service.get_hierarchy_tree(school_id, hierarchy_id)
        report = await service.get_consolidated_report(school_id, hierarchy_id)
        
        return {
            "status": "success",
            "format": format,
            "hierarchy_id": hierarchy_id,
            "tree": tree,
            "report": report,
            "export_timestamp": "now",
        }
    except AccountHierarchyError as e:
        logger.warning(f"Error exporting hierarchy: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in export: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export hierarchy data")
