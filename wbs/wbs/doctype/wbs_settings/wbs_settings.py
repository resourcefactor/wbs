# -*- coding: utf-8 -*-
# Copyright (c) 2022, yashwanth and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document
import datetime

class WBSSettings(Document):
	pass

@frappe.whitelist()
def get_doc_url():
	try:
		doc = frappe.new_doc('WBS Settings')
		url = doc.get_url()
		return {'url': url}
	except Exception as ex:
		return {'EX': ex}


@frappe.whitelist()
def get_nearest_settings_id(transaction_date, warehouse):
	try:
		list = frappe.db.sql("""select twsl.name from `tabWBS Settings` as tws
							join `tabWBS Storage Location` as twsl on twsl.wbs_settings_id = tws.name
							where tws.warehouse=%s and tws.start_date<=%s and twsl.attribute_level = '4'
							order by tws.start_date desc""", (warehouse, transaction_date), as_dict=1);
		print(list)

		if list and len(list) > 0:
			return {'list': list}

		return False
	except Exception as ex:
		return {"EX": ex}

@frappe.whitelist()
def is_wbs(warehouse):
	try:
		list = frappe.db.sql("""select is_wbs_active from `tabWarehouse` where name = %s""", warehouse, as_dict = 1)

		print(list)
		if list and len(list):
			if list[len(list) - 1].is_wbs_active == 1:
				return {'is_wbs_active': 1}
			else:
				return {'is_wbs_active': 0}
		return False
	except Exception as ex:
		return {'EX': ex}


@frappe.whitelist()
def get_relative_settings(transaction_date, warehouse, item_code):
	try:
		list = frappe.db.sql("""select twsl.name from `tabWBS Stored Items` as twsi
							join `tabWBS Storage Location` as twsl on twsl.name = twsi.parent
							join `tabWBS Settings` as tws on tws.name = twsl.wbs_settings_id
							where (tws.start_date<=%s and tws.warehouse = %s)
							and (twsl.rarb_warehouse = %s and twsi.item_code = %s)
							and (twsl.attribute_level = '4' and twsl.is_group = '0')""",
							(transaction_date, warehouse, warehouse, item_code), as_dict =1);

		print(list)

		if list and len(list) > 0:
			return {'list': list}

		return False
	except Exception as ex:
		return {'EX': ex}


@frappe.whitelist()
def check_stock_ledger_entry_for_transactions(doc):
	try:
		stock_entry = json.loads(doc)

		if stock_entry.get('purpose') == 'Material Transfer' or stock_entry.get('purpose') == 'Material Issue':
			posting_date = stock_entry.get('posting_date')

			if stock_entry.get('items') and len(stock_entry.get('items')) > 0:
				for i in stock_entry.get('items'):
					s_wbs = check_wbs(i.get('s_warehouse'))

					if s_wbs == 1:
						warehouse = i.get('s_warehouse')
						item_code = i.get('item_code')
						strg_loc = i.get('source_warehouse_storage_location')
						list = get_entries(warehouse, posting_date, item_code, strg_loc)

						if list:

							if int(list.get('qty_after_transaction')) == 0:
								return {'Error': 'quantity available in source warehouse storage location {0} at row : {1} is : {2}'.format(strg_loc,i.get('idx'), int(list.get('qty_after_transaction')))}

							is_quantity_available = int(list.get('qty_after_transaction') - i.get('qty'))

							if is_quantity_available < 0:
								return {'Error': 'quantity not available in source warehouse storage location {0} at row : {1}'.format(strg_loc,i.get('idx'))}
							else:
								return False
						else:
							return {'Error': 'quantity not available in source warehouse storage location {0} at row : {1}'.format(strg_loc,i.get('idx'))}

		# elif stock_entry.get('Material Receipt') == 'Material Receipt':
		# 	posting_date = stock_entry.get('posting_date')
		#
		# 	if stock_entry.get('items') and len(stock_entry.get('items')) > 0:
		# 		for i in stock_entry.get('items'):
		# 			warehouse = i.get('t_warehouse')
		# 			item_code = i.get('item_code')
		# 			strg_loc = i.get('target_warehouse_storage_location')
		#
		# 			list = frappe.db.sql("""select sle.item_code, se.purpose, sle.actual_qty, sle.qty_after_transaction, sle.posting_date, sle.posting_time from `tabStock Ledger Entry` as sle
		# 								join `tabStock Entry` as se on se.name = sle.voucher_no
		# 								join `tabStock Entry Detail` as sed on sed.parent = se.name
		# 								where (sle.warehouse = %s and sle.posting_date <= %s)
		# 								and (sle.item_code = %s and sed.target_warehouse_storage_location = %s)
		# 								group by sle.item_code
		# 								order by sle.posting_time desc""", (warehouse, posting_date, item_code, strg_loc), as_dict = 1);
		#
		# 			if list and len(list) > 0:
		# 				for l in list:
		# 					is_quantity_available = int(l.get('qty_after_transaction') - i.get('qty'))
		#
		# 					if is_quantity_available == 0 or is_quantity_available < 0:
		# 						return {'Error': 'quantity not available in source warehouse storage location {0} at row : {1}'.format(strg_loc,i.get('idx'))}
		# 					else:
		# 						return False
		# 			else:
		# 				return False

		return {"SC": False}
	except Exception as ex:
		return {'EX': ex}


def check_wbs(warehouse):
	try:
		if warehouse:
			list = frappe.db.sql("""select is_wbs_active from `tabWarehouse` where name = %s""", warehouse, as_dict = 1)

			if list and len(list):
				if list[len(list) - 1].is_wbs_active == 1:
					return 1
				else:
					return 0
			else:
				return 0
		else:
			return 0
	except Exception as ex:
		return ex


def get_entries(warehouse, posting_date, item_code, strg_loc):
	try:
		list = frappe.db.sql("""select sle.item_code, se.purpose, sle.actual_qty, sle.qty_after_transaction, sle.posting_date, sle.posting_time from `tabStock Ledger Entry` as sle
							join `tabStock Entry` as se on se.name = sle.voucher_no
							join `tabStock Entry Detail` as sed on sed.parent = se.name
							where (sle.warehouse = %s and sle.posting_date <= %s)
							and (sle.item_code = %s and (sed.source_warehouse_storage_location= %s or sed.target_warehouse_storage_location=%s))
							order by DATE(sle.posting_date) desc, sle.posting_time desc""", (warehouse, posting_date, item_code, strg_loc, strg_loc), as_dict = 1);

		if list and len(list) > 0:
			return list[len(list) - len(list)]
		else:
			return False
	except Exception as ex:
		return ex

@frappe.whitelist()
def get_storage_location(date, warehouse):
	try:
		list  = frappe.db.sql("""select twsl.name from `tabWBS Storage Location` as twsl
							join `tabWBS Settings` as tws on tws.name = twsl.wbs_settings_id
							where (tws.start_date<=%s and tws.warehouse = %s)
							and (twsl.rarb_warehouse = %s)
							and (twsl.attribute_level = '4' and twsl.is_group = '1')""", (date, warehouse, warehouse),as_dict = 1)
		print(list)
		if list and len(list) > 0:
			return {"list": list}
		return False
	except Exception as ex:
		return {'EX': ex}


@frappe.whitelist()
def get_previous_transaction(date, warehouse, item_code):
	try:
		print('previous transaction')
		list = frappe.db.sql("""select sle.item_code, sed.target_warehouse_storage_location, sle.posting_date, sle.posting_time, sle.actual_qty, sle.qty_after_transaction, sle.voucher_no from `tabStock Ledger Entry` as sle
							join `tabStock Entry Detail` as sed on sed.parent = sle.voucher_no
							where sle.posting_date<= %s and sle.warehouse = %s and sle.item_code = %s
							order by DATE(sle.posting_date) desc, sle.posting_time desc""", (date, warehouse, item_code), as_dict = 1);

		if list and len(list) > 0:
			transaction = list[len(list) - len(list)]

			if transaction:
				if transaction.get('target_warehouse_storage_location') and int(transaction.get('qty_after_transaction')) > 0:
					doc = frappe.get_doc('WBS Storage Location', transaction.get('target_warehouse_storage_location'))

					if doc:
						settings = frappe.get_doc('WBS Settings', doc.wbs_settings_id)

						if settings:
							doc_list = frappe.db.sql("""select sle.item_code, sed.target_warehouse_storage_location, se.purpose, sle.actual_qty, sle.qty_after_transaction, sle.posting_date, sle.posting_time from `tabStock Ledger Entry` as sle
													join `tabStock Entry` as se on se.name = sle.voucher_no
													join `tabStock Entry Detail` as sed on sed.parent = se.name
													where (sle.warehouse = %s and (sle.posting_date <= %s and sle.posting_date >= %s))
													and (sle.item_code = %s and sed.target_warehouse_storage_location=%s)
													order by DATE(sle.posting_date) desc, sle.posting_time desc""",(warehouse, date, settings.start_date, item_code, doc.name), as_dict = 1);

							if doc_list and len(doc_list) > 0:
								return {'list': doc_list[len(doc_list) - len(doc_list)]}
							else:
								return False
						else:
							return False
					else:
						return False

				else:
					return False
			else:
				return False
		return False
	except Exception as ex:
		return {'EX': ex}
