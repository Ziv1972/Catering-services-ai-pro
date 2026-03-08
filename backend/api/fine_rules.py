"""
Fine rules API endpoints — predefined fine catalog for complaints.
Includes AI-powered import from uploaded documents (PDF/Excel/etc).
"""
import logging
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.models.complaint import FineRule, ComplaintCategory
from backend.models.attachment import Attachment
from backend.api.auth import get_current_user
from backend.api.attachments import extract_file_content
from backend.services.claude_service import claude_service

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_CATEGORIES = [c.value for c in ComplaintCategory]


class FineRuleResponse(BaseModel):
    id: int
    name: str
    category: str
    amount: float
    description: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class FineRuleCreate(BaseModel):
    name: str
    category: str
    amount: float
    description: Optional[str] = None


class FineRuleUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


# ── Import schemas ──


class ExtractedFineRule(BaseModel):
    name: str
    category: str
    amount: float
    description: Optional[str] = None


class ImportPreviewRequest(BaseModel):
    attachment_id: int


class ImportPreviewResponse(BaseModel):
    rules: List[ExtractedFineRule]
    source_filename: str
    total_count: int


class ImportConfirmRequest(BaseModel):
    rules: List[ExtractedFineRule]
    deactivate_existing: bool = True


@router.get("/", response_model=List[FineRuleResponse])
async def list_fine_rules(
    category: Optional[str] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(FineRule)
    if active_only:
        query = query.where(FineRule.is_active == True)
    if category:
        query = query.where(FineRule.category == category)
    query = query.order_by(FineRule.category, FineRule.amount.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=FineRuleResponse)
async def create_fine_rule(
    data: FineRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = FineRule(**data.model_dump(), is_active=True)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=FineRuleResponse)
async def update_fine_rule(
    rule_id: int,
    data: FineRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(FineRule).where(FineRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Fine rule not found")

    for key, value in data.model_dump(exclude_none=True).items():
        setattr(rule, key, value)

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
async def delete_fine_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(FineRule).where(FineRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Fine rule not found")

    rule.is_active = False
    await db.commit()
    return {"message": "Fine rule deactivated"}


# ── AI Import from Document ──


@router.post("/import-preview", response_model=ImportPreviewResponse)
async def import_preview(
    body: ImportPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extract fine rules from an uploaded document using AI. Returns preview — no DB changes."""
    result = await db.execute(
        select(Attachment).where(Attachment.id == body.attachment_id)
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(404, "Attachment not found")

    logger.info(
        f"Import preview: attachment {att.id}, file='{att.original_filename}', "
        f"path='{att.file_path}', content_type='{att.content_type}'"
    )

    if not att.file_path or not os.path.exists(att.file_path):
        raise HTTPException(
            400,
            f"File '{att.original_filename}' not found on server. "
            "This can happen after a redeployment. Please re-upload the document."
        )

    file_text = extract_file_content(att.file_path, att.content_type, att.original_filename)

    if not file_text or not file_text.strip():
        raise HTTPException(
            400,
            f"Cannot extract text from '{att.original_filename}'. "
            "Supported: PDF, Excel, CSV, TXT files."
        )

    # Detect extraction errors returned as strings
    if file_text.startswith("[") and file_text.endswith("]"):
        logger.error(f"File extraction error for '{att.original_filename}': {file_text}")
        raise HTTPException(
            400,
            f"Error reading file: {file_text}. "
            "Please ensure the file is a valid PDF, Excel, or text document."
        )

    logger.info(
        f"Extracted {len(file_text)} chars from '{att.original_filename}'. "
        f"First 200 chars: {file_text[:200]!r}"
    )

    truncated = file_text[:30_000]
    categories_str = ", ".join(VALID_CATEGORIES)

    prompt = (
        "Below is text extracted from a Hebrew fine/penalty document for a catering contract.\n"
        "Extract ALL fine rules / penalty clauses from this document.\n\n"
        "For each rule, provide:\n"
        "- name: Short descriptive name in English (translate from Hebrew)\n"
        f"- category: MUST be exactly one of: {categories_str}\n"
        "- amount: Fine amount in NIS (number only). If a range, use the maximum. "
        "If percentage-based, estimate a reasonable fixed amount.\n"
        "- description: Brief description in English (translate from Hebrew), "
        "include the original Hebrew term in parentheses if relevant\n\n"
        f"Document text:\n{truncated}"
    )

    system_prompt = (
        "You are a legal document analyst specializing in Israeli catering contracts. "
        "Extract structured penalty/fine rules from Hebrew contract documents. "
        "Translate Hebrew to English for names and descriptions. "
        "Map each rule to the most appropriate category from the allowed list. "
        "Be thorough — extract every distinct fine rule mentioned."
    )

    response_format = {
        "rules": [
            {"name": "string", "category": "string", "amount": 0, "description": "string"}
        ]
    }

    try:
        extracted = await claude_service.generate_structured_response(
            prompt=prompt,
            system_prompt=system_prompt,
            response_format=response_format,
        )
        logger.info(f"Claude response for import: {extracted}")
    except Exception as e:
        logger.error(f"AI extraction failed for attachment {body.attachment_id}: {e}")
        raise HTTPException(500, "AI extraction failed. Please try again.")

    if not extracted or not isinstance(extracted, dict):
        logger.error(f"Unexpected AI response type: {type(extracted)}, value: {extracted}")
        raise HTTPException(500, "AI returned unexpected response format. Please try again.")

    rules: List[ExtractedFineRule] = []
    raw_rules = extracted.get("rules", [])
    if not isinstance(raw_rules, list):
        logger.error(f"Expected list for 'rules', got {type(raw_rules)}: {raw_rules}")
        raw_rules = []

    for r in raw_rules:
        cat = r.get("category", "other")
        if cat not in VALID_CATEGORIES:
            cat = "other"
        rules.append(ExtractedFineRule(
            name=r.get("name", "Unknown rule"),
            category=cat,
            amount=float(r.get("amount", 0)),
            description=r.get("description"),
        ))

    logger.info(
        f"Extracted {len(rules)} fine rules from '{att.original_filename}' "
        f"for user {current_user.id}"
    )

    return ImportPreviewResponse(
        rules=rules,
        source_filename=att.original_filename,
        total_count=len(rules),
    )


@router.post("/import-confirm")
async def import_confirm(
    body: ImportConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Replace existing fine rules with AI-extracted ones. Deactivates old rules, creates new."""
    if not body.rules:
        raise HTTPException(400, "No rules to import")

    deactivated_count = 0
    if body.deactivate_existing:
        existing_result = await db.execute(
            select(FineRule).where(FineRule.is_active == True)
        )
        existing_rules = existing_result.scalars().all()
        deactivated_count = len(existing_rules)
        for rule in existing_rules:
            rule.is_active = False

    created: List[FineRule] = []
    for r in body.rules:
        cat = r.category if r.category in VALID_CATEGORIES else "other"
        new_rule = FineRule(
            name=r.name,
            category=cat,
            amount=r.amount,
            description=r.description,
            is_active=True,
        )
        db.add(new_rule)
        created.append(new_rule)

    await db.commit()

    for rule in created:
        await db.refresh(rule)

    logger.info(
        f"User {current_user.id} imported {len(created)} fine rules "
        f"(deactivated {deactivated_count} old rules)"
    )

    return {
        "success": True,
        "deactivated_count": deactivated_count,
        "imported_count": len(created),
        "rules": [
            {
                "id": r.id,
                "name": r.name,
                "category": r.category if isinstance(r.category, str) else r.category.value,
                "amount": r.amount,
                "description": r.description,
            }
            for r in created
        ],
    }
