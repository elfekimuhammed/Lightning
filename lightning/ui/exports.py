"""Explicit downloads of the posted cash activity shown in the register."""

import csv
import io

from fastapi.responses import Response


def _text(value):
    text = str(value or "")
    # Text fields must stay text when a downloaded CSV is opened in a spreadsheet.
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")) else text


def register_csv(c, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Date", "Transaction ID", "Reference", "Type", "Account ID", "Account",
                     "Currency", "Counterparty", "Category", "Amount", "Description", "Notes",
                     "Other account ID", "Other account", "Money held for"])
    accounts = {a.id: a for a in c.accounts.list()}
    for row in rows:
        writer.writerow([row.date, row.txn_id, _text(row.ref), row.type, row.account_id,
                         _text(row.account_label), accounts[row.account_id].currency,
                         _text(row.counterparty), _text(row.category_label), format(row.amount, "f"),
                         _text(row.description), _text(row.notes), row.other_account_id or "",
                         _text(row.other_account_label),
                         _text(c.money_from_others.transaction_owner(row.txn_id))])
    return Response(output.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="lightning-activity.csv"',
                             "Cache-Control": "no-store"})
