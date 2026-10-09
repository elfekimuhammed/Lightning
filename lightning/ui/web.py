"""FastAPI app factory. The UI only calls services/workflows — no SQL, no financial math."""

from __future__ import annotations

import contextvars
from dataclasses import replace

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from starlette.middleware.trustedhost import TrustedHostMiddleware

from lightning import DISPLAY_VERSION
from lightning.bootstrap import Container
from lightning.core.dates import fmt_date, month_of, today
from lightning.core.errors import NotFoundError, ValidationError
from lightning.core.figures import FIGURES
from lightning.core.memo import request_cache
from lightning.core.money import ZERO, fmt, to_decimal
from lightning.workflows import live_prices
from lightning.ui import sections

UI_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(UI_DIR / "templates"))

# UI language is profile-scoped; financial values and user supplied names are never translated.
ARABIC_UI = {
    'Overview': 'نظرة عامة',
    'Budget': 'ميزانيتك',
    'Birdview': 'الصورة المالية',
    'Investments': 'الاستثمارات',
    'Expenses': 'المصروفات',
    'Cash': 'الكاش',
    'Reserves': 'المبالغ المحجوزة',
    'Financial health': 'صحتك المالية',
    'Accounts': 'حساباتك',
    'People': 'الأشخاص',
    'Search': 'بحث',
    'Hide amounts': 'إخفاء المبالغ',
    'Show amounts': 'إظهار المبالغ',
    'Profiles & lock': 'الملفات الشخصية والقفل',
    'Add account': 'أضف حساب',
    'Manage accounts': 'إدارة الحسابات',
    'Back': 'رجوع',
    'Hand back': 'رجّع للهاتف',
    'Devices': 'الأجهزة',
    'Settings': 'الإعدادات',
    'Main navigation': 'التنقل الرئيسي',
    'Sections': 'الأقسام',
    'Tools': 'الأدوات',
    'English': 'الإنجليزية',
    'العربية': 'العربية',
    'Language': 'اللغة',
    'Your data': 'بياناتك',
    'App version': 'إصدار التطبيق',
    'Base currency': 'العملة الأساسية',
    'Back up now': 'نسخ احتياطي الآن',
    'Database file': 'ملف قاعدة البيانات',
    'A backup is made automatically each time the app starts.': 'يُنشأ نسخ احتياطي تلقائيًا عند بدء التطبيق.',
    'Summary': 'الملخص',
    'Spending': 'الإنفاق',
    'Health': 'الصحة',
    'Cash planning': 'تخطيط النقدية',
    'Plan': 'الخطة',
    'Recurring': 'المتكرر',
    'Loans': 'القروض',
    'Holdings': 'المقتنيات',
    'Planner': 'المخطط',
    'Prices': 'الأسعار',
    'Transactions': 'المعاملات',
    'Held for others': 'أموال لغيرك',
    'Categories': 'الفئات',
    'Counterparties': 'الأطراف المقابلة',
    'Rules': 'القواعد',
    'Data checks': 'فحوصات البيانات',
    'Sale factors': 'عوامل التسييل',
    'Financial health limits': 'حدود الصحة المالية',
    'Budget settings': 'إعدادات الميزانية',
    'Financial assets': 'الأصول المالية',
    'Target allocation': 'التوزيع المستهدف',
    'Price files': 'ملفات الأسعار',
    'Get set up': 'ظبّط حسابك',
    'Your position': 'مركزك المالي',
    'As of': 'حتى',
    'Cash flow': 'التدفق النقدي',
    'Month by month': 'شهرًا بشهر',
    'Your spending plan': 'خطة مصروفاتك',
    'Set your first spending limit': 'حدّد أول مبلغ لمصروفاتك',
    'Start with a broad monthly amount. You can refine categories below after saving.': 'ابدأ بمبلغ شهري تقريبي، وبعد الحفظ تقدر تضبط كل فئة لوحدها.',
    'Saved and invested': 'المدخر والمستثمر',
    'Spent of plan': 'المنفق من الخطة',
    'Spending by group': 'الإنفاق حسب المجموعة',
    'Where is your money held?': 'فلوسك موجودة فين؟',
    'No holdings yet': 'لا توجد مقتنيات بعد',
    'Valued as of': 'القيمة حتى',
    'Intended investment horizon': 'الأفق الاستثماري المقصود',
    'How is safe to spend worked out?': 'إزاي بنحسب المبلغ الآمن للصرف؟',
    'Where is my cash heading?': 'فلوسي رايحة فين؟',
    'What is promised?': 'ما الالتزامات القادمة؟',
    'This period': 'هذه الفترة',
    'In your accounts': 'في حساباتك',
    'What you own': 'اللي تملكه',
    'Bank and wallet cash': 'نقدية البنك والمحفظة',
    'Brokerage cash': 'نقدية الاستثمار',
    'Cash you own': 'النقدية اللي تملكها',
    'Deposits': 'الودائع والشهادات',
    'Holdings value': 'قيمة الاستثمارات',
    'Other you own': 'أصول تانية تملكها',
    'Bills due': 'فواتير مستحقة',
    'Loans still to pay': 'قروض لسه عليك',
    'What you owe': 'اللي عليك',
    'Net worth': 'صافي ثروتك',
    'Bills and subscriptions a month': 'الفواتير والاشتراكات شهريًا',
    'Loan payments a month': 'أقساط القروض شهريًا',
    'Debt to net worth': 'الديون مقارنة بصافي ثروتك',
    'Debt to cash': 'الديون مقارنة بالنقدية',
    'Loan payments to income': 'أقساط القروض من دخلك',
    'Fixed costs to income': 'المصاريف الثابتة من دخلك',
    'Free cash': 'النقدية المتاحة',
    'Portfolio value': 'قيمة المحفظة',
    'Holdings after sale (estimate)': 'قيمة الاستثمارات بعد البيع (تقديري)',
    'If you sold today (estimate)': 'لو بعت النهارده (تقديري)',
    'Money in': 'فلوس داخلة',
    'Money out': 'فلوس خارجة',
    'Income': 'الدخل',
    'Emergency fund': 'صندوق الطوارئ',
    'Net flow': 'صافي التدفق',
    'Savings rate': 'نسبة الادخار',
    'Opening balances in the period': 'أرصدة بداية الفترة',
    'Change in what you own': 'التغير في اللي تملكه',
    'Change in net worth': 'التغير في صافي ثروتك',
    'Per month': 'شهريًا',
    'Usual month': 'الشهر المعتاد',
    'Usual range': 'النطاق المعتاد',
    'Investing rate': 'نسبة الاستثمار',
    'Average monthly income': 'متوسط الدخل الشهري',
    'Average monthly spending': 'متوسط المصروفات الشهرية',
    'Base budget': 'الميزانية الأساسية',
    'Carryover': 'المبلغ المرحّل',
    'Planned': 'المخطط',
    'Spent': 'المنفق',
    'Left in plan': 'المتبقي في الخطة',
    'Plan leaves to save': 'المتبقي للادخار من الخطة',
    'Planned savings rate': 'نسبة الادخار المخططة',
    'Savings target': 'هدف الادخار',
    'Emergency fund top-up': 'زيادة صندوق الطوارئ',
    'Saving needed': 'المطلوب ادخاره',
    'Most you can plan': 'أقصى مبلغ تقدر تخطط له',
    'Cost': 'التكلفة',
    'Unrealized gain': 'ربح غير محقق',
    'Price change on what you hold': 'تغير قيمة المقتنيات',
    'Gain from sales': 'أرباح البيع',
    'Dividends and interest': 'توزيعات وفوائد',
    'Net gain or loss': 'صافي الربح أو الخسارة',
    'Money added': 'فلوس مضافة',
    'Typical move': 'الحركة المعتادة',
    'Fall from its high': 'الانخفاض من أعلى قيمة',
    'Average cost': 'متوسط التكلفة',
    'Growth': 'النمو',
    'Safe to spend': 'المتاح الآمن للصرف',
    'Bills inside the plan': 'الفواتير ضمن الخطة',
    'Budget left to spend': 'المتبقي من الميزانية للصرف',
    'Bills and loan payments before next income': 'الفواتير والأقساط قبل الدخل القادم',
    'Saving for goals': 'الادخار للأهداف',
    'Rest of savings target': 'باقي هدف الادخار',
    'Create plan': 'اعمل الخطة',
    'Spending group': 'مجموعة المصروفات',
    'Monthly limit': 'الحد الشهري',
    'Open categories': 'افتح الفئات',
    'Undo': 'تراجع',
    'Select all': 'اختار الكل',
    'Track': 'تابع',
    'Not now': 'مش دلوقتي',
    'One-off': 'مرة واحدة',
    'Cancel': 'إلغاء',
    'Save': 'حفظ',
    'Add an account': 'أضف حساب',
    'Edit account': 'تعديل الحساب',
    'Type': 'النوع',
    'Currency': 'العملة',
    'Starting balance': 'الرصيد الافتتاحي',
    'Balance': 'الرصيد',
    'Held for': 'مملوك لـ',
    'More details': 'تفاصيل أكتر',
    'Notes': 'ملاحظات',
    'Choose date': 'اختار التاريخ',
    'Add recurring item': 'أضف بند متكرر',
    'Bills and subscriptions': 'فواتير واشتراكات',
    'Every month': 'كل شهر',
    'Recurring items': 'بنود متكررة',
    'Add salary and bills': 'أضف المرتب والفواتير',
    'Review': 'مراجعة',
    'Use': 'استخدم',
    'No more payments': 'مفيش مدفوعات تانية',
    'Show the numbers': 'اعرض الأرقام',
    'Create': 'إنشاء',
    'Update': 'تحديث',
    'Delete': 'حذف',
    'Add transaction': 'أضف معاملة',
    'Record transaction': 'سجّل معاملة',
    'Open accounts': 'افتح الحسابات',
    'Ref': 'الرقم المرجعي',
    'What': 'الوصف',
    'Date': 'التاريخ',
    'Account': 'الحساب',
    'Category': 'الفئة',
    'Amount': 'المبلغ',
    'No transactions yet.': 'لسه مفيش معاملات.',
    'Name': 'الاسم',
    'Institution': 'البنك أو الجهة',
    'Last 4 digits': 'آخر ٤ أرقام',
    'Optional. Never enter the full number.': 'اختياري. ما تكتبش الرقم كامل.',
    'yyyy-mm-dd': 'سنة-شهر-يوم',
    'Today': 'النهارده',
    'Yesterday': 'امبارح',
    'All': 'الكل',
    'All time': 'كل الوقت',
    'YTD': 'من أول السنة',
    'Monthly': 'شهريًا',
    'Custom': 'فترة مخصصة',
    'Previous month': 'الشهر اللي فات',
    'Next month': 'الشهر الجاي',
    'Month': 'الشهر',
    'Month, yyyy-mm': 'الشهر، سنة-شهر',
    'From month': 'من شهر',
    'To month': 'لحد شهر',
    'Apply': 'تطبيق',
    'New account': 'حساب جديد',
    'An account is a place where money is held.': 'الحساب هو المكان اللي بتحتفظ فيه بفلوسك.',
    'Shown under': 'بيظهر تحت',
    'Accounts are kept in your base currency for now.': 'الحسابات بتتسجل حاليًا بعملتك الأساسية.',
    'Enter what this account held when you started tracking it. This sets the opening balance; it is not counted as income. Leave it blank if you’ll import or enter the opening activity separately.': 'اكتب رصيد الحساب لما بدأت تتابعه. ده رصيد افتتاحي ومش بيتحسب دخل. سيبه فاضي لو هتستورد أو تسجل الحركات الافتتاحية لوحدها.',
    'You': 'أنت',
    'Leave blank if you own this starting balance.': 'سيبه فاضي لو الرصيد ده ملكك.',
    'Transfer': 'تحويل',
    'Transaction type': 'نوع المعاملة',
    'Record one account activity. Enter a positive amount; choose Money out, Money in, or Transfer.': 'سجّل حركة واحدة على الحساب. اكتب مبلغ موجب واختار فلوس خارجة أو داخلة أو تحويل.',
    'Transfer to': 'تحويل إلى',
    'Choose an account': 'اختار حساب',
    'Choose a category': 'اختار فئة',
    'Counterparty': 'الطرف الآخر',
    'optional': 'اختياري',
    'Type a person or business': 'اكتب اسم شخص أو شركة',
    'Choose a saved Counterparty.': 'اختار طرفًا آخر محفوظًا.',
    'Check the date.': 'راجع التاريخ.',
    'Choose a spending category': 'اختار فئة مصروفات',
    'Set a category…': 'حدّد فئة…',
    'Category for the selected rows': 'فئة الصفوف المختارة',
    'Edit transaction': 'تعديل المعاملة',
    'New expense': 'مصروف جديد',
    'New income': 'دخل جديد',
    'New transfer': 'تحويل جديد',
    'e.g.': 'مثال:',
    'e.g. CIB Current': 'مثال: حساب البنك التجاري',
    'e.g. CIB': 'مثال: البنك التجاري',
    'Enter a name': 'اكتب الاسم',
    'Optional': 'اختياري',
}


def translate(text: str, locale: str = "en") -> str:
    return ARABIC_UI.get(str(text), str(text)) if locale == "ar" else str(text)


def localized_figures(locale: str):
    """Keep shared figure names consistent across every template and report."""
    return {key: replace(figure, label=translate(figure.label, locale), meaning=translate(figure.meaning, locale))
            for key, figure in FIGURES.items()}


def _minus(text: str) -> str:
    """Screens show a true minus (−5,000.00); exports keep the ASCII hyphen."""
    return "\u2212" + text[1:] if text.startswith("-") else text


# Reporting pages show money rounded to the nearest unit; stored values, entry fields and registers
# keep their decimals. A template that asks for places explicitly (an input's value) gets them.
_ROUND_MONEY: contextvars.ContextVar[bool] = contextvars.ContextVar("round_money", default=False)
REPORTING_TEMPLATES = ("dashboard/", "budget.html", "birdview/", "investments/index.html", "investments/holding.html", "financial_health.html",
                       "investments/_targets.html", "investments/targets.html", "investments/report_detail.html",
                       "planning/plan.html", "reserves.html", "settings/index.html")


def _money(value, signed: bool = False, places: int | None = None) -> str:
    if places is None:
        places = 0 if _ROUND_MONEY.get() else 2
    if value is None or isinstance(value, Decimal):
        return _minus(fmt(value, places, signed))
    # Re-rendered forms hand back what the user typed ("45,000.00", "−450");
    # show it as typed instead of failing the whole page.
    text = str(value).strip().replace(",", "").replace("\u2212", "-")
    try:
        return _minus(fmt(Decimal(text), places, signed))
    except InvalidOperation:
        return str(value)


def _tone(value) -> str:
    if value is None:
        return ""
    return "neg" if value < ZERO else ("pos" if value > ZERO else "zero")


def _keep_dates(text) -> Markup:
    """Dates never break across lines (a narrow key note would split 2026-10-03 at a hyphen)."""
    return Markup(re.sub(r"\b(\d{4}-\d{2}(?:-\d{2})?)\b", r'<span class="nowrap">\1</span>', str(escape(text))))


templates.env.filters["money"] = _money
templates.env.filters["tr"] = translate


def _tagged(text) -> Markup:
    """A note with each #tag a link to every transaction that carries it."""
    from lightning.transactions.tags import split
    link = Markup('<a class="note-tag" href="/transactions?tag={}">{}</a>')
    return Markup("").join(link.format(quote(tag), piece) if tag else escape(piece)
                           for piece, tag in split(str(text or "")))


templates.env.filters["tagged"] = _tagged


def _phone_chip(text) -> str:
    """A KPI chip on a phone says its period in a few characters (guideline C06.1) and is never cut (C12):
    "until 2026-11-01" -> "2026-11-01", "2026-07 to 2026-09" -> "3 months". Text that would still be cut
    returns "", so the tile shows no chip rather than half a word."""
    import re as _re
    value = str(text or "").strip()
    if found := _re.fullmatch(r"(?:until |to )(\d{4}-\d{2}-\d{2})", value):
        return found.group(1)
    if found := _re.fullmatch(r"(\d{4})-(\d{2})(?:-\d{2})? to (\d{4})-(\d{2})(?:-\d{2})?", value):
        months = (int(found.group(3)) - int(found.group(1))) * 12 + int(found.group(4)) - int(found.group(2)) + 1
        return f"{months} months" if months > 1 else f"{found.group(1)}-{found.group(2)}"
    return value if len(value) <= 10 and not (" " in value and len(value) > 8) else ""


templates.env.filters["phone_chip"] = _phone_chip


def _signed_pct(value, places: int = 1) -> str:
    """A signed percentage to one decimal ("+6.2", "−1.5"); a value that rounds to zero reads "0.0",
    never "−0.0" or "+0.0" (audit 2026-10-05: a certificate's XIRR showed −0.0%)."""
    text = f"{value:+.{places}f}"
    return text[1:] if float(text) == 0 else text.replace("-", "\u2212")


templates.env.filters["signed_pct"] = _signed_pct
templates.env.filters["tone"] = _tone
templates.env.filters["keep_dates"] = _keep_dates


def _units(value) -> str:
    """A quantity with no trailing zeros: 25 units, 1 piece, 12.5 g, 1,250 shares."""
    if value is None:
        return ""
    text = f"{Decimal(value):,.4f}".rstrip("0").rstrip(".")
    return text


templates.env.filters["units"] = _units


def _units_of(value, unit: str) -> str:
    """A quantity with its unit, singular for exactly one: 75 shares, 1 piece, 12.5 grams."""
    if value is None:
        return ""
    unit = (unit or "").strip()
    plural = unit and Decimal(value) != 1 and not unit.endswith("s") and unit.upper() != unit
    return f"{_units(value)} {unit}{'s' if plural else ''}".strip()


templates.env.filters["units_of"] = _units_of


def _compact(value) -> str:
    """A short whole number for tight cells: 950, 9.7k, 12k, 1.2M (signed values keep a −)."""
    if value is None:
        return "—"
    v = Decimal(value)
    sign, v = ("−" if v < 0 else ""), abs(v)
    if v >= 1_000_000:
        text = f"{v / 1_000_000:.1f}M"
    elif v >= 10_000:
        text = f"{v / 1000:.0f}k"
    elif v >= 1000:
        text = f"{v / 1000:.1f}k"
    else:
        text = f"{v:.0f}"
    return sign + text.replace(".0k", "k").replace(".0M", "M")


templates.env.filters["compact"] = _compact
templates.env.globals["abs"] = abs


# Pages reached from many places with no Back of their own; the main tabs are left out on purpose.
_REFERER_BACK_PAGES = ("/transactions", "/investments/holding", "/investments/planner", "/investments/prices")


def _back_url(request) -> str:
    """Where a full page's Back button goes: the page it was opened from (``return_to``), only if
    it is a page of this app. Empty when there is nowhere to go back to."""
    raw = str(request.query_params.get("return_to", "") or "")
    if not raw and request.url.path.startswith(_REFERER_BACK_PAGES):
        # The desktop window has no browser Back: detail pages opened from a chart, a row or a
        # report fall back to the in-app page that linked here (same origin only, checked below).
        raw = str(request.headers.get("referer", "") or "")
    parts = urlsplit(raw)
    if parts.netloc and parts.netloc != request.url.netloc:
        return ""
    path = parts.path or ""
    if not path.startswith("/") or path.startswith("//") or path == request.url.path:
        return ""
    query = "&".join(q for q in parts.query.split("&") if q and not q.startswith("popup="))
    return path + (f"?{query}" if query else "")


templates.env.globals["back_url"] = _back_url
templates.env.globals["sections_for"] = sections.for_request
templates.env.globals["fig"] = FIGURES
def build_version(identity: Path = Path(__file__).resolve().parents[1] / "build_identity.txt") -> str:
    """The version Settings shows: the build's own name when the build wrote one (the phone test build
    writes `<version>-test.<commits>+<commit>`), else the source version."""
    try:
        return identity.read_text(encoding="utf-8").strip() or DISPLAY_VERSION
    except OSError:
        return DISPLAY_VERSION


templates.env.globals["app_version"] = build_version()


def container(request: Request) -> Container:
    current = request.app.state.container
    if current is None:
        raise RuntimeError("Financial routes require an unlocked profile")
    return current


PRIVACY_COOKIE = "lightning_privacy"


def privacy_on(request: Request) -> bool:
    """Privacy mode: the window's choice for this sitting, else what the profile remembers. The window
    runs in private mode, so its cookie ends with it; a reader session, which cannot save, keeps the cookie."""
    cookie = request.cookies.get(PRIVACY_COOKIE)
    if cookie in ("0", "1"):
        return cookie == "1"
    current = request.app.state.container
    return current is not None and current.settings.get("privacy_mode") == "1"


templates.env.globals["privacy_on"] = privacy_on


def render(request: Request, name: str, status_code: int = 200, **context) -> HTMLResponse:
    c = container(request)
    context.setdefault("msg", request.query_params.get("msg", ""))
    note = live_prices.apply_finished(c)  # month-end prices fetched in the background since the profile opened
    if note:
        context["msg"] = f"{context['msg']} {note}".strip()
    context.setdefault("error", "")
    context.setdefault("error_field", "")
    total, owned_total, groups = c.reporting.sidebar(today())
    token = _ROUND_MONEY.set(name.startswith(REPORTING_TEMPLATES))
    try:
        return _render(request, name, status_code, c, total, owned_total, groups, context)
    finally:
        _ROUND_MONEY.reset(token)


_PHONE: contextvars.ContextVar[bool] = contextvars.ContextVar("lightning_phone", default=False)
_PHONE_TEMPLATES: set[str] | None = None


def phone_mode() -> bool:
    """Whether this page renders for the phone app (guideline Part C); for macros, which have no request."""
    return _PHONE.get()


templates.env.globals["phone_mode"] = phone_mode


def _phone_template(name: str) -> str:
    """A page with its own phone screen has it under templates/phone/; every other page keeps its own."""
    global _PHONE_TEMPLATES
    if _PHONE_TEMPLATES is None:
        _PHONE_TEMPLATES = {t for t in templates.env.list_templates() if t.startswith("phone/")}
    return f"phone/{name}" if f"phone/{name}" in _PHONE_TEMPLATES else name


def _render(request, name, status_code, c, total, owned_total, groups, context) -> HTMLResponse:
    phone = bool(getattr(request.state, "phone", False))
    if phone:
        name = _phone_template(name)
    marker = _PHONE.set(phone)
    try:
        return _render_page(request, name, status_code, c, total, owned_total, groups, context)
    finally:
        _PHONE.reset(marker)


def _render_page(request, name, status_code, c, total, owned_total, groups, context) -> HTMLResponse:
    locale = c.settings.get("locale") if c is not None else "en"
    locale = locale if locale in ("en", "ar") else "en"
    return templates.TemplateResponse(
        request,
        name,
        {
            "base": c.base_currency,
            "locale": locale,
            "fig": localized_figures(locale),
            "today": fmt_date(today()),
            "this_month": month_of(today()),
            "path": request.url.path,
            "sidebar_total": total,
            "sidebar_owned_total": owned_total,
            "sidebar_groups": groups,
            "csrf": getattr(request.state, "csrf", ""),
            "session_epoch": getattr(request.state, "session_epoch", ""),
            "session_token": getattr(request.state, "session_token", ""),
            "category_groups": c.categories.select_groups,
            "prices_running": live_prices.running(c),
            **context,
        },
        status_code=status_code,
    )


def redirect(url: str, msg: str = "") -> RedirectResponse:
    if msg:
        url += ("&" if "?" in url else "?") + "msg=" + quote(msg)
    return RedirectResponse(url, status_code=303)


# Pages whose header has the period control, and what they remember of it.
PERIOD_PAGES = {"/", "/budget", "/birdview/expenses", "/investments"}
PERIOD_KEYS = ("period", "month", "date_from", "date_to")
PERIOD_COOKIE = "lightning_period"


class RequestCache:
    """Each request computes a repeated figure once (``lightning.core.memo``); a write empties it."""

    def __init__(self, app, state):
        self.app, self.state = app, state

    async def __call__(self, scope, receive, send):
        current = getattr(self.state, "container", None) if scope["type"] == "http" else None
        if current is None:
            return await self.app(scope, receive, send)
        with request_cache(current.db):
            await self.app(scope, receive, send)


def create_app(c: Container | None = None) -> FastAPI:
    from .routes import accounts, bank_imports, birdview, budget, categories, counterparties, dashboard, deposits, exports, financial_health, integrity, investments, physical_items, planning, reserves, rules, search, settings, sms, transactions

    app = FastAPI(title="Lightning", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.container = c
    app.add_middleware(TrustedHostMiddleware,
                       allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])

    @app.middleware("http")
    async def same_origin_posts(request: Request, call_next):
        if request.method == "POST":
            host = request.headers.get("host", "").lower()
            for header in ("origin", "referer"):
                value = request.headers.get(header)
                if value and urlsplit(value).netloc.lower() != host:
                    return PlainTextResponse("Cross-origin form submission blocked.", status_code=403)
        return await call_next(request)

    @app.middleware("http")
    async def remembered_period(request: Request, call_next):
        """The period picked in a page header carries over to every page that has one."""
        if request.method != "GET" or request.url.path not in PERIOD_PAGES or request.headers.get("x-lightning-popup"):
            return await call_next(request)
        picked = {k: v for k, v in request.query_params.items() if k in PERIOD_KEYS}
        if not picked:
            saved = dict(parse_qsl(request.cookies.get(PERIOD_COOKIE, "")))
            seen_in = saved.pop("seen_in", "")
            now = month_of(today())
            if saved.get("period", "month") == "month" and saved.get("month") == seen_in and seen_in != now:
                saved["month"] = now   # "this month" moves on with the calendar; a month picked from the past stays
            if saved:  # same page, with the remembered period added to whatever else was asked for
                return RedirectResponse(f"{request.url.path}?{urlencode({**dict(request.query_params), **saved})}", status_code=303)
            return await call_next(request)
        response = await call_next(request)
        if response.status_code == 200:  # only a period that worked is remembered
            response.set_cookie(PERIOD_COOKIE, urlencode({**picked, "seen_in": month_of(today())}),
                                httponly=True, samesite="strict")
        return response

    @app.get("/__health", include_in_schema=False)
    async def health():
        return PlainTextResponse("lightning-ok")

    @app.get("/amount-sum", include_in_schema=False)
    async def amount_sum(text: str = ""):
        """A sum typed in an amount field (120+35*2), worked out so the field shows 190 before saving."""
        try:
            value = to_decimal(text)
        except ValidationError as error:
            return JSONResponse({"error": error.message})
        return JSONResponse({"value": format(value.normalize(), "f")})

    app.mount("/static", StaticFiles(directory=str(UI_DIR / "static")), name="static")
    for module in (dashboard, financial_health, accounts, deposits, bank_imports, birdview, transactions, budget, investments, physical_items, planning, reserves, integrity, counterparties, categories, rules, settings, search, exports, sms):
        app.include_router(module.router)

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, exc: NotFoundError):
        return render(request, "not_found.html", status_code=404, message=exc.message)

    app.add_middleware(RequestCache, state=app.state)  # outermost, so every page and middleware shares it
    return app
