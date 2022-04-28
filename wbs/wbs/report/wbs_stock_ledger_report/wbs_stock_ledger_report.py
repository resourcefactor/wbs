# Copyright (c) 2013, yashwanth and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint, flt
from datetime import datetime
from erpnext.stock.utils import update_included_uom_in_report
from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos
from wbs.wbs.doctype.wbs_settings.wbs_settings import get_start_date, get_end_date, get_warehouse
from wbs.wbs.doctype.wbs_storage_location.wbs_storage_location import get_storage_location, get_entry_detail, get_id

def execute(filters=None):
	include_uom = filters.get("include_uom")
	columns = get_columns()
	items = get_items(filters)
	sl_entries = get_stock_ledger_entries(filters, items)
	item_details = get_item_details(items, sl_entries, include_uom)
	opening_row = get_opening_balance(filters, columns)
	precision = cint(frappe.db.get_single_value("System Settings", "float_precision"))

	data = []
	conversion_factors = []
	if opening_row:
		data.append(opening_row)

	actual_qty = stock_value = 0

	validate_date(filters)

	available_serial_nos = {}
	for sle in sl_entries:

		item_detail = item_details[sle.item_code]
		sle.update(item_detail)

		if filters.get("batch_no"):
			actual_qty += flt(sle.actual_qty, precision)
			stock_value += sle.stock_value_difference

			if sle.voucher_type == 'Stock Reconciliation' and not sle.actual_qty:
				actual_qty = sle.qty_after_transaction
				stock_value = sle.stock_value

			sle.update({
				"qty_after_transaction": actual_qty,
				"stock_value": stock_value
			})

		if sle.serial_no:
			update_available_serial_nos(available_serial_nos, sle)

		data.append(sle)

		if include_uom:
			conversion_factors.append(item_detail.conversion_factor)

	update_included_uom_in_report(columns, data, include_uom, conversion_factors)

	if filters.get('wbs_settings'):
		data = update_wbs_storage_location(data, filters)

	return columns, data


def validate_date(filters):
	if filters.get('wbs_settings'):
		actual_from_date = get_start_date(filters.get('wbs_settings'))
		actual_to_date = get_end_date(filters.get('wbs_settings'))
		selected_from_date = datetime.strptime(filters.get('from_date'), '%Y-%m-%d').date() if filters.get('from_date') else ''
		selected_to_date = datetime.strptime(filters.get('to_date'), '%Y-%m-%d').date() if filters.get('to_date') else ''

		# if actual_from_date.get('from_date') and actual_to_date.get('to_date'):
		# 	if selected_from_date < actual_from_date.get('from_date') or selected_from_date > actual_to_date.get('to_date') or selected_to_date > actual_to_date.get('to_date') or selected_to_date < actual_from_date.get('from_date'):
		# 		frappe.throw(_('From and To date should be between WBS Settings Duration'))
		# if actual_from_date.get('from_date') and actual_to_date.get('INFINITE'):
		# 	if selected_from_date < actual_from_date.get('from_date'):
		# 		frappe.throw(_('From and To date should be between WBS Settings Duration'))

	return

# Filter to sort the stock ledger report for wbs storage location.
# EDIT this when specific to WBS Storage location.
def update_wbs_storage_location(data, filters):
	rpt = []
	entry_detail = []

	warehouse = get_warehouse(filters.get('wbs_settings')).get('warehouse') if get_warehouse(filters.get('wbs_settings')).get('warehouse') else False
	ID = filters.get('wbs_settings')

	if ID:
		# Fetches list of all the WBS Storage Locations for the selected WBS Settings ID.
		locations = get_storage_location(ID)

	if data:
		for d in data:
			if d.get('voucher_no') and warehouse:
				# Fetches the Stock Entry Details for WBS Transaction by VOUCHER_NO.
				details = get_entry_detail(d.get('voucher_no'), warehouse, d.get('item_code'), d.get('voucher_detail_no'))
				if details:
					entry_detail.append(details)

	if entry_detail:
		for e in entry_detail:
			for d in data:
				if e.get('parent') == d.get('voucher_no') and e.get('name') == d.get('voucher_detail_no'):
					if warehouse == e.get('s_warehouse') and d.get('item_code') == e.get('item_code'):
						id = get_id(e.get('source_warehouse_storage_location'))
						if id:
							d.update({
								'wbs_storage_location': e.get('source_warehouse_storage_location'),
								'wbs_id': id
							})
					if warehouse == e.get('t_warehouse') and d.get('item_code') == e.get('item_code'):
						id = get_id(e.get('target_warehouse_storage_location'))
						if id:
							d.update({
								'wbs_storage_location': e.get('target_warehouse_storage_location'),
								'wbs_id': id
							})
	for d in data:
		if d.get('voucher_no') and d.get('wbs_storage_location') and d.get('wbs_id'):
			rpt.append(d);

	return rpt

def update_available_serial_nos(available_serial_nos, sle):
	serial_nos = get_serial_nos(sle.serial_no)
	key = (sle.item_code, sle.warehouse)
	if key not in available_serial_nos:
		available_serial_nos.setdefault(key, [])

	existing_serial_no = available_serial_nos[key]
	for sn in serial_nos:
		if sle.actual_qty > 0:
			if sn in existing_serial_no:
				existing_serial_no.remove(sn)
			else:
				existing_serial_no.append(sn)
		else:
			if sn in existing_serial_no:
				existing_serial_no.remove(sn)
			else:
				existing_serial_no.append(sn)

	sle.balance_serial_no = '\n'.join(existing_serial_no)

def get_columns():
	columns = [
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Datetime", "width": 95},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "width": 100},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 100},
		{"label": _("WBS Storage Location"), "fieldname": "wbs_storage_location", "fieldtype": "Link", "options": "WBS Storage Location", "width": 150},
		{"label": _("WBS ID"), "fieldname": "wbs_id", "width":150},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 100},
		{"label": _("Description"), "fieldname": "description", "width": 200},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 100},
		{"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 100},
		{"label": _("Qty"), "fieldname": "actual_qty", "fieldtype": "Float", "width": 50, "convertible": "qty"},
		{"label": _("Balance Qty"), "fieldname": "qty_after_transaction", "fieldtype": "Float", "width": 100, "convertible": "qty"},
		{"label": _("Incoming Rate"), "fieldname": "incoming_rate", "fieldtype": "Currency", "width": 110,
			"options": "Company:company:default_currency", "convertible": "rate"},
		{"label": _("Valuation Rate"), "fieldname": "valuation_rate", "fieldtype": "Currency", "width": 110,
			"options": "Company:company:default_currency", "convertible": "rate"},
		{"label": _("Balance Value"), "fieldname": "stock_value", "fieldtype": "Currency", "width": 110,
			"options": "Company:company:default_currency"},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "width": 110},
		{"label": _("Voucher #"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 100},
		{"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 100},
		{"label": _("Serial No"), "fieldname": "serial_no", "width": 100},
		{"label": _("Balance Serial No"), "fieldname": "balance_serial_no", "width": 100},
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 100},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 110}
	]

	return columns


def get_stock_ledger_entries(filters, items):
	item_conditions_sql = ''
	if items:
		item_conditions_sql = 'and sle.item_code in ({})'\
			.format(', '.join([frappe.db.escape(i) for i in items]))

	return frappe.db.sql("""select concat_ws(" ", sle.posting_date, sle.posting_time) as date,
			sle.item_code, sle.warehouse, sle.actual_qty, sle.qty_after_transaction, sle.incoming_rate, sle.valuation_rate,
			sle.stock_value, sle.voucher_type, sle.voucher_no,sle.voucher_detail_no, sle.batch_no, sle.serial_no, sle.company, sle.project, sle.stock_value_difference
		from `tabStock Ledger Entry` as sle
		where sle.company = %(company)s and
			sle.posting_date between %(from_date)s and %(to_date)s
			{sle_conditions}
			{item_conditions_sql}
			order by sle.posting_date asc, sle.posting_time asc, sle.creation asc"""\
		.format(
			sle_conditions=get_sle_conditions(filters),
			item_conditions_sql = item_conditions_sql
		), filters, as_dict=1)

def get_items(filters):
	conditions = []
	if filters.get("item_code"):
		conditions.append("item.name=%(item_code)s")
	else:
		if filters.get("brand"):
			conditions.append("item.brand=%(brand)s")
		if filters.get("item_group"):
			conditions.append(get_item_group_condition(filters.get("item_group")))

	items = []
	if conditions:
		items = frappe.db.sql_list("""select name from `tabItem` item where {}"""
			.format(" and ".join(conditions)), filters)
	return items

def get_item_details(items, sl_entries, include_uom):
	item_details = {}
	if not items:
		items = list(set([d.item_code for d in sl_entries]))

	if not items:
		return item_details

	cf_field = cf_join = ""
	if include_uom:
		cf_field = ", ucd.conversion_factor"
		cf_join = "left join `tabUOM Conversion Detail` ucd on ucd.parent=item.name and ucd.uom=%s" \
			% frappe.db.escape(include_uom)

	res = frappe.db.sql("""
		select
			item.name, item.item_name, item.description, item.item_group, item.brand, item.stock_uom {cf_field}
		from
			`tabItem` item
			{cf_join}
		where
			item.name in ({item_codes})
	""".format(cf_field=cf_field, cf_join=cf_join, item_codes=','.join(['%s'] *len(items))), items, as_dict=1)

	for item in res:
		item_details.setdefault(item.name, item)

	return item_details

def get_sle_conditions(filters):
	conditions = []
	if filters.get("warehouse"):
		warehouse_condition = get_warehouse_condition(filters.get("warehouse"))
		if warehouse_condition:
			conditions.append(warehouse_condition)
	if filters.get("voucher_no"):
		conditions.append("sle.voucher_no=%(voucher_no)s")
	if filters.get("batch_no"):
		conditions.append("sle.batch_no=%(batch_no)s")
	if filters.get("project"):
		conditions.append("sle.project=%(project)s")

	return "and {}".format(" and ".join(conditions)) if conditions else ""

def get_opening_balance(filters, columns):
	if not (filters.item_code and filters.warehouse and filters.from_date):
		return

	from erpnext.stock.stock_ledger import get_previous_sle
	last_entry = get_previous_sle({
		"item_code": filters.item_code,
		"warehouse_condition": get_warehouse_condition(filters.warehouse),
		"posting_date": filters.from_date,
		"posting_time": "00:00:00"
	})
	row = {}
	row["item_code"] = _("'Opening'")
	for dummy, v in ((9, 'qty_after_transaction'), (11, 'valuation_rate'), (12, 'stock_value')):
			row[v] = last_entry.get(v, 0)

	return row

def get_warehouse_condition(warehouse):
	warehouse_details = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"], as_dict=1)
	if warehouse_details:
		return " exists (select name from `tabWarehouse` wh \
			where wh.lft >= %s and wh.rgt <= %s and warehouse = wh.name)"%(warehouse_details.lft,
			warehouse_details.rgt)

	return ''

def get_item_group_condition(item_group):
	item_group_details = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"], as_dict=1)
	if item_group_details:
		return "item.item_group in (select ig.name from `tabItem Group` ig \
			where ig.lft >= %s and ig.rgt <= %s and item.item_group = ig.name)"%(item_group_details.lft,
			item_group_details.rgt)

	return ''
