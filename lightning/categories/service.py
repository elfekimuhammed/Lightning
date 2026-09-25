"""Public API of the categories module."""

from __future__ import annotations

from dataclasses import replace

from lightning.core.codes import path_segment, validate_path_code
from lightning.core.errors import ConflictError, NotFoundError, ValidationError
from lightning.database.connection import Database

from .domain import Category, Movement
from .repository import CategoryRepository


class CategoryService:
    def __init__(self, db: Database):
        self.db = db
        self.repo = CategoryRepository(db)

    # -- reading -----------------------------------------------------------
    def tree(self, movement: Movement | None = None, active_only: bool = False) -> list[Category]:
        """Categories in tree order (parent, then its children)."""
        cats = self.repo.list()
        by_parent: dict[int | None, list[Category]] = {}
        for c in cats:
            by_parent.setdefault(c.parent_id, []).append(c)
        ordered: list[Category] = []

        def walk(parent_id: int | None, parent_active: bool) -> None:
            for child in by_parent.get(parent_id, []):
                visible = parent_active and child.active
                if movement and child.movement != movement:
                    continue
                if active_only and not visible:
                    continue
                ordered.append(child)
                walk(child.id, visible)

        walk(None, True)
        return ordered

    def pickable(self, movement: Movement) -> list[Category]:
        """What a user can choose on a form: active, not a top-level root, not system-only."""
        return [c for c in self.tree(movement, active_only=True) if not c.is_root and not c.is_system]

    def get(self, category_id: int) -> Category:
        found = self.repo.get(category_id)
        if not found:
            raise NotFoundError("Category not found.")
        return found

    def get_by_code(self, code: str) -> Category:
        found = self.repo.get_by_code(code)
        if not found:
            raise NotFoundError(f"Category {code} not found.")
        return found

    def display_name(self, category_id: int) -> str:
        """Names only, for screens: 'Personal › Food & Groceries' (the Expenses/Income root is implied)."""
        names, current = [], self.get(category_id)
        while current.parent_id is not None:
            names.append(current.name)
            current = self.get(current.parent_id)
        return " › ".join(reversed(names)) or current.name

    def find_by_text(self, text: str) -> Category:
        """What someone typed in the Category box -> the category. Accepts the full name
        ('Personal › Food & Groceries'), the plain name ('Food & Groceries') or the code; case does not matter."""
        wanted = " ".join((text or "").split()).casefold()
        if not wanted:
            raise ValidationError("Choose a category — or pick one of your accounts in To for a transfer.",
                                  "category")
        options = [c for c in self.tree(active_only=True) if not c.is_root and not c.is_system]
        for key in (lambda c: self.display_name(c.id), lambda c: c.name, lambda c: c.code):
            matches = [c for c in options if key(c).casefold() == wanted]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                names = " or ".join(self.display_name(c.id) for c in matches)
                raise ValidationError(f"Which one — {names}?", "category")
        partial = [c for c in options if wanted in self.display_name(c.id).casefold()]
        if len(partial) == 1:
            return partial[0]
        if partial:
            names = ", ".join(self.display_name(c.id) for c in partial[:4])
            raise ValidationError(f"'{text}' matches several categories: {names}. Pick one from the list.",
                                  "category")
        raise ValidationError(f"There is no category called '{text}'. Pick one from the list, or add it under "
                              "Categories.", "category")

    def groups(self, movement: Movement, include_inactive: bool = True) -> list[tuple[Category, list[Category]]]:
        """Second-level groups (Personal, Work, Fees…) with everything beneath them, for the categories page."""
        items = [c for c in self.tree(movement) if not c.is_root and not c.is_system]
        if not include_inactive:
            items = [c for c in items if c.active]
        result: list[tuple[Category, list[Category]]] = []
        for c in items:
            if c.depth == 1:
                result.append((c, []))
            elif result:
                result[-1][1].append(c)
        return result

    def descendants(self, category_id: int) -> list[Category]:
        root = self.get(category_id)
        return [c for c in self.repo.list() if c.code.startswith(root.code + ".")]

    def require(self, category_id: int | None, movement: Movement) -> Category:
        """Validate that a category can be used for this direction of money."""
        if category_id is None:
            raise ValidationError("Choose a category.", "category")
        cat = self.get(category_id)
        if cat.movement != movement:
            wanted = "money in" if movement == Movement.INFLOW else "money out"
            raise ValidationError(f"{cat.label} is not a {wanted} category.", "category")
        if not cat.active:
            raise ValidationError(f"{cat.label} is inactive.", "category")
        if cat.is_root:
            raise ValidationError("Choose a more specific category than the top level.", "category")
        return cat

    # -- writing -----------------------------------------------------------
    def create(
        self,
        parent_id: int,
        name: str,
        code: str | None = None,
        default_reimbursable: bool | None = None,
    ) -> Category:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Enter a name.", "name")
        parent = self.get(parent_id)
        code = self._child_code(parent, code or path_segment(name))
        if self.repo.code_exists(code):
            raise ConflictError(f"The code {code} is already used.", "code")
        cat = Category(
            id=0,
            code=code,
            name=name,
            parent_id=parent.id,
            movement=parent.movement,
            scope=parent.scope,
            income_class=parent.income_class,
            default_reimbursable=(
                parent.default_reimbursable if default_reimbursable is None else default_reimbursable
            ),
            is_system=False,
            active=True,
            sort_order=self.repo.next_sort_order(),
        )
        with self.db.transaction():
            new_id = self.repo.insert(cat)
        return self.get(new_id)

    def update(
        self,
        category_id: int,
        name: str,
        code: str | None = None,
        active: bool = True,
        default_reimbursable: bool | None = None,
    ) -> list[int]:
        """Update a category (a code change carries over to its sub-categories). Returns the ids changed."""
        cat = self.get(category_id)
        name = (name or "").strip()
        if not name:
            raise ValidationError("Enter a name.", "name")
        new_code = cat.code
        if code and validate_path_code(code) != cat.code:
            if cat.is_root or cat.is_system:
                raise ValidationError("This category's code is fixed.", "code")
            parent = self.get(cat.parent_id)  # type: ignore[arg-type]
            new_code = self._child_code(parent, validate_path_code(code).rsplit(".", 1)[-1])
            if self.repo.code_exists(new_code, exclude_id=cat.id):
                raise ConflictError(f"The code {new_code} is already used.", "code")
        if not active and (cat.is_root or cat.is_system):
            raise ValidationError("This category cannot be deactivated.", "active")
        changed = [cat.id]
        with self.db.transaction():
            if new_code != cat.code:
                for child in self.descendants(cat.id):
                    self.repo.update(replace(child, code=new_code + child.code[len(cat.code):]))
                    changed.append(child.id)
            self.repo.update(
                replace(
                    cat,
                    name=name,
                    code=new_code,
                    active=active,
                    default_reimbursable=(
                        cat.default_reimbursable if default_reimbursable is None else default_reimbursable
                    ),
                )
            )
        return changed

    @staticmethod
    def _child_code(parent: Category, segment: str) -> str:
        segment = validate_path_code(segment)
        if segment.startswith(parent.code + "."):
            segment = segment[len(parent.code) + 1 :]
        if "." in segment:
            raise ValidationError("A category code adds one part to its parent's code.", "code")
        return f"{parent.code}.{segment}"
