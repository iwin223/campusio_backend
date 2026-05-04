"""Account Hierarchy Models

Handles hierarchical GL account structures and balance rollup.

Supports:
- Multi-level account hierarchies
- Parent-child account relationships
- Balance rollup from detail to summary accounts
- Consolidated reporting by hierarchy level
"""
from sqlmodel import SQLModel, Field
from sqlalchemy import JSON
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid
import json


class AccountHierarchyType(str, Enum):
    """Type of account hierarchy"""
    ACCOUNT_LEVEL = "account_level"      # By account type (Asset, Liability, Equity, etc.)
    ORGANIZATIONAL = "organizational"    # By organizational unit (department, cost center)
    FUNCTIONAL = "functional"            # By function (operations, academics, admin)
    PROGRAM = "program"                  # By program or fund
    CUSTOM = "custom"                    # User-defined hierarchy


class HierarchyLevel(str, Enum):
    """Position in hierarchy"""
    DETAIL = "detail"              # Lowest level, individual GL accounts
    SUMMARY = "summary"            # Intermediate rollup accounts
    TOTAL = "total"                # Highest level, full consolidation


class AccountHierarchy(SQLModel, table=True):
    """Account Hierarchy - Definition of account structure
    
    Defines a specific hierarchy structure (e.g., "Organization Structure",
    "Cost Center Allocation", "Departmental Rollup").
    """
    __tablename__ = "account_hierarchies"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # Hierarchy identification
    hierarchy_name: str  # Name of hierarchy (e.g., "Organizational Structure")
    hierarchy_type: AccountHierarchyType = Field(index=True)
    description: Optional[str] = None
    
    # Hierarchy definition
    is_active: bool = Field(default=True, index=True)
    allow_detail_posting: bool = Field(default=True)  # Can post to detail-level accounts
    auto_rollup_enabled: bool = Field(default=True)  # Auto-calculate parent balances
    
    # Metadata
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = None


class HierarchyNode(SQLModel, table=True):
    """Hierarchy Node - Account node in the hierarchy tree
    
    Represents a node in the account hierarchy structure. Can be a detail account
    (leaf node), summary account (intermediate), or total account (root).
    """
    __tablename__ = "hierarchy_nodes"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # References
    hierarchy_id: str = Field(index=True)  # FK to AccountHierarchy
    gl_account_id: Optional[str] = None  # FK to GLAccount (null for summary-only nodes)
    parent_node_id: Optional[str] = None  # FK to parent HierarchyNode
    
    # Node information
    node_name: str  # Display name for this node
    node_code: str = Field(index=True)  # Hierarchical code (e.g., "1.1.1" for 3 levels)
    level: HierarchyLevel = Field(index=True)  # Detail, Summary, or Total
    sequence: int = 0  # Display order within parent
    
    # Balance tracking
    current_balance: float = 0.0  # Rollup balance (sum of children or detail account balance)
    opening_balance: float = 0.0  # Opening balance for period
    
    # Hierarchy structure
    is_parent: bool = Field(default=False)  # This node has children
    children_count: int = 0  # Number of child nodes
    
    # Settings
    include_in_consolidation: bool = Field(default=True)
    exclude_from_posting: bool = Field(default=False)  # Prevents posting to this level
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class HierarchyRelationship(SQLModel, table=True):
    """Hierarchy Relationship - Parent-child account linkage
    
    Explicitly defines the parent-child relationships in the hierarchy.
    Allows for flexible account structures.
    """
    __tablename__ = "hierarchy_relationships"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # References
    hierarchy_id: str = Field(index=True)
    parent_node_id: str = Field(index=True)  # FK to parent HierarchyNode
    child_node_id: str = Field(index=True)  # FK to child HierarchyNode
    
    # Relationship details
    child_sequence: int = 0  # Order of child within parent
    contribution_percentage: float = 100.0  # What % of child goes to parent (default 100%)
    
    # Validation
    is_active: bool = Field(default=True, index=True)
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class HierarchyRollup(SQLModel, table=True):
    """Hierarchy Rollup - Pre-calculated rollup balance snapshot
    
    Stores pre-calculated rollup balances at specific points in time
    for reporting and performance optimization.
    """
    __tablename__ = "hierarchy_rollups"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # References
    hierarchy_node_id: str = Field(index=True)
    hierarchy_id: str = Field(index=True)
    
    # Rollup data
    rollup_date: datetime = Field(index=True)  # Date of rollup
    total_balance: float = 0.0  # Sum of all descendant detail accounts
    child_count: int = 0  # Number of child nodes included
    detail_count: int = 0  # Number of detail accounts in subtree
    
    # Rollup details
    contribution_from_children: Optional[str] = Field(default=None, sa_type=JSON)  # JSON: child contributions
    
    # Audit
    calculated_by: str
    calculation_timestamp: datetime = Field(default_factory=datetime.utcnow)


class HierarchyConsolidation(SQLModel, table=True):
    """Hierarchy Consolidation - Full hierarchy rollup for a period
    
    Represents a complete rollup calculation for reporting purposes.
    """
    __tablename__ = "hierarchy_consolidations"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    school_id: str = Field(index=True)
    
    # References
    hierarchy_id: str = Field(index=True)
    period_id: Optional[str] = None  # FK to FiscalPeriod (if period-specific)
    
    # Consolidation details
    consolidation_date: datetime = Field(index=True)
    is_complete: bool = Field(default=False)  # All nodes calculated
    
    # Validation
    is_balanced: bool = Field(default=False)  # Root total = sum of all posted transactions
    validation_errors: Optional[str] = None  # Any validation issues found
    
    # Audit
    consolidated_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==================== Request/Response Models ====================

class HierarchyNodeCreate(SQLModel):
    """Validation model for creating hierarchy node"""
    hierarchy_id: str
    node_name: str
    node_code: str
    level: HierarchyLevel
    parent_node_id: Optional[str] = None
    gl_account_id: Optional[str] = None
    sequence: int = 0


class HierarchyNodeResponse(SQLModel):
    """Response model for hierarchy node"""
    id: str
    hierarchy_id: str
    node_name: str
    node_code: str
    level: HierarchyLevel
    parent_node_id: Optional[str]
    current_balance: float
    opening_balance: float
    children_count: int
    is_parent: bool


class HierarchyRelationshipCreate(SQLModel):
    """Validation model for hierarchy relationship"""
    hierarchy_id: str
    parent_node_id: str
    child_node_id: str
    child_sequence: int = 0
    contribution_percentage: float = 100.0


class HierarchyTreeResponse(SQLModel):
    """Response model for hierarchy tree"""
    id: str
    node_name: str
    node_code: str
    current_balance: float
    level: HierarchyLevel
    children: Optional[List["HierarchyTreeResponse"]] = None


class RollupReportResponse(SQLModel):
    """Response model for rollup report"""
    hierarchy_id: str
    hierarchy_name: str
    rollup_date: datetime
    total_balance: float
    detail_count: int
    by_level: Dict
