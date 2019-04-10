function initialize() {
	build_tables_and_groups();
	group_div = document.getElementById('groups');
	table_div = document.getElementById('tables');
	for (var i = 0; i < groups.length; i++) {
		add_group(groups[i]);
	}
	for (var i = 0; i < tables.length; i++) {
		add_table(tables[i], table_div, null);
	}
	mark_clean();
}

function build_tables_and_groups() {
	var ntables = 0;
	for (var i = 0; i < groups.length; i++) {
		groups[i].guest_nums = [];
	}
	for (var i = 0; i < guests.length; i++) {
		var guest = guests[i];
		if (guest.table_num > ntables)
			ntables = guest.table_num;
	}
	for (var i = 0; i < ntables; i++) {
		var new_table = {
			table_num: i + 1,
			seating_prefs: "",
			checked: false,
			guest_nums: []
		};
		tables.push(new_table);
	}
	for (var i = 0; i < guests.length; i++) {
		var guest = guests[i];
		if (guest.table_num > 0) {
			var table = tables[guest.table_num - 1];
			table.guest_nums.push(guest.guest_num);
		} else {
			var group = groups[guest.group_num - 1];
			group.guest_nums.push(guest.guest_num);
		}
	}
}

function mark_clean() {
	var save_button = document.getElementById('save_button');
	save_button.disabled = true;
}

function mark_dirty() {
	var save_button = document.getElementById('save_button');
	save_button.disabled = false;
}

function update_set(the_set, n, is_checked) {
	var pos;
	for (pos = 0; pos < the_set.length; pos++) {
		if (the_set[pos] >= n)
			break;
	}
	if (is_checked && pos >= the_set.length) {
		the_set.push(n);
	} else if (is_checked && the_set[pos] != n) {
		the_set.splice(pos, 0, n);
	} else if (!is_checked && pos < the_set.length && the_set[pos] == n) {
		the_set.splice(pos, 1);
	}
}

function top_onchange_handler(topbox, subboxes, group_num, table_num) {
	return function() {
		var is_checked = topbox.checked;
		for (var i = 0; i < subboxes.length; i++) {
			var guest_num = parseInt(subboxes[i].value);
			subboxes[i].checked = is_checked;
			if (table_num > 0)
				update_set(assigned_guests_selected, guest_num, is_checked);
			else if (group_num > 0)
				update_set(unassigned_guests_selected, guest_num, is_checked);
		}
		if (table_num > 0) {
			update_set(tables_selected, table_num, is_checked);
		} else if (group_num > 0) {
			update_set(groups_selected, group_num, is_checked);
		}
	}
}

function sub_onchange_handler(topbox, subboxes, group_num, table_num, n) {
	return function() {
		var num_checked = 0;
		var guest_num = parseInt(subboxes[n].value);
		var is_checked = subboxes[n].checked;
		if (table_num > 0)
			update_set(assigned_guests_selected, guest_num, is_checked);
		else if (group_num > 0)
			update_set(unassigned_guests_selected, guest_num, is_checked);
		for (var i = 0; i < subboxes.length; i++) {
			if (subboxes[i].checked)
				num_checked++;
		}
		if (num_checked == subboxes.length) {
			topbox.checked = true;
			if (table_num > 0) {
				update_set(tables_selected, table_num, true);
			} else if (group_num > 0) {
				update_set(groups_selected, group_num, true);
			}
		} else if (num_checked == 0) {
			topbox.checked = false;
			if (table_num > 0) {
				update_set(tables_selected, table_num, false);
			} else if (group_num > 0) {
				update_set(groups_selected, group_num, false);
			}
		}
	}
}

function install_checkbox_handlers(topbox, subboxes, group_num, table_num) {
	topbox.onchange = top_onchange_handler(topbox, subboxes, group_num, table_num);
	for (var i = 0; i < subboxes.length; i++) {
		subboxes[i].onchange = sub_onchange_handler(topbox, subboxes, group_num, table_num, i);
	}
}

function make_group(group) {
	var div = document.createElement("div");
	div.setAttribute("class", "group");

	var contact = document.createElement("p");
	contact.setAttribute("class", "contact");
	var topbox = document.createElement("input");
	topbox.setAttribute("id", "group_" + group.group_num + "_box");
	topbox.setAttribute("class", "group_checkbox");
	topbox.setAttribute("type", "checkbox");
	topbox.setAttribute("name", "groups_selected");
	topbox.setAttribute("value", group.group_num.toString());
	contact.appendChild(topbox);
	contact.appendChild(document.createTextNode(" "));
	var label = document.createElement("label");
	label.setAttribute("for", "group_" + group.group_num + "_box");
	var name = document.createTextNode(group.first_name + " " + group.last_name);
	label.appendChild(name);
	contact.appendChild(label);
	contact.appendChild(document.createTextNode(" "));
	var id = document.createElement("span");
	id.setAttribute("class", "id");
	id.appendChild(document.createTextNode("("));
	var anchor = document.createElement("a");
	anchor.setAttribute("href", "/register?id=" + group.id);
	anchor.appendChild(document.createTextNode(group.id));
	id.appendChild(anchor);
	id.appendChild(document.createTextNode(")"));
	contact.appendChild(id);
	div.appendChild(contact);

	var subboxes = []
	var ul = document.createElement("ul");
	for (var i = 0; i < group.guest_nums.length; i++) {
		var guest_num = group.guest_nums[i];
		var guest = guests[guest_num - 1];
		var li = document.createElement("li");

		var subbox = document.createElement("input");
		subbox.setAttribute("id", "guest_" + guest.guest_num + "_box");
		subbox.setAttribute("class", "guest_checkbox");
		subbox.setAttribute("type", "checkbox");
		subbox.setAttribute("name", "unassigned_guests_selected");
		subbox.setAttribute("value", guest.guest_num.toString());
		li.appendChild(subbox);
		subboxes.push(subbox);

		li.appendChild(document.createTextNode(" "));

		label = document.createElement("label");
		label.setAttribute("for", "guest_" + guest.guest_num + "_box");
		name = document.createElement("span");
		name.setAttribute("class", "guestname");
		name.appendChild(document.createTextNode(guest.guest_name));
		label.appendChild(name);
		li.appendChild(label);

		ul.appendChild(li);
	}
	div.appendChild(ul);

	if (group.seating_prefs != "") {
		var prefs = document.createElement("p");
		prefs.setAttribute("class", "prefs");
		prefs.appendChild(document.createTextNode("Seating preference: " + group.seating_prefs));
		div.appendChild(prefs);
	}

	install_checkbox_handlers(topbox, subboxes, group.group_num, 0);
	return div;
}

function add_group(group) {
	if (group.guest_nums.length == 0) {
		group.group_elem = null;
		return;
	}
	var elem = make_group(group);
	if (group.group_num + 1 < groups.length) {
		var next = groups[group.group_num + 1].group_elem;
		group_div.insertBefore(elem, next);
	} else {
		group_div.appendChild(elem);
	}
	group.group_elem = elem;
}

function make_table(table) {
	var div = document.createElement("div");
	div.setAttribute("class", "table");

	var contact = document.createElement("p");
	contact.setAttribute("class", "contact");
	var topbox = document.createElement("input");
	topbox.setAttribute("id", "table_" + table.table_num + "_box");
	topbox.setAttribute("class", "table_checkbox");
	topbox.setAttribute("type", "checkbox");
	topbox.setAttribute("name", "tables_selected");
	topbox.setAttribute("value", table.table_num.toString());
	contact.appendChild(topbox);
	contact.appendChild(document.createTextNode(" "));
	var label = document.createElement("label");
	label.setAttribute("for", "table_" + table.table_num + "_box");
	var name = document.createTextNode("Table " + table.table_num);
	label.appendChild(name);
	contact.appendChild(label);
	div.appendChild(contact);

	var subboxes = []
	var ul = document.createElement("ul");
	for (var i = 0; i < table.guest_nums.length; i++) {
		var guest_num = table.guest_nums[i];
		var guest = guests[guest_num - 1];
		var li = document.createElement("li");

		var subbox = document.createElement("input");
		subbox.setAttribute("id", "guest_" + guest.guest_num + "_box");
		subbox.setAttribute("class", "guest_checkbox");
		subbox.setAttribute("type", "checkbox");
		subbox.setAttribute("name", "assigned_guests_selected");
		subbox.setAttribute("value", guest.guest_num.toString());
		li.appendChild(subbox);
		subboxes.push(subbox);

		li.appendChild(document.createTextNode(" "));

		label = document.createElement("label");
		label.setAttribute("for", "guest_" + guest.guest_num + "_box");
		name = document.createElement("span");
		name.setAttribute("class", "guestname");
		name.appendChild(document.createTextNode(guest.guest_name));
		label.appendChild(name);
		li.appendChild(label);

		ul.appendChild(li);
	}
	div.appendChild(ul);

	if (table.seating_prefs != "") {
		var prefs = document.createElement("p");
		prefs.setAttribute("class", "prefs");
		prefs.appendChild(document.createTextNode("Seating preference: " + table.seating_prefs));
		div.appendChild(prefs);
	}

	install_checkbox_handlers(topbox, subboxes, 0, table.table_num);
	return div;
}

function add_table(table, parent, replace) {
	var elem = make_table(table);
	var before = null;
	if (replace) {
		before = replace.nextSibling;
		parent.removeChild(replace);
	}
	if (before)
		parent.insertBefore(elem, before);
	else
		parent.appendChild(elem);
	table.table_elem = elem;
}

function clear_selections(prefix, selections) {
	for (i = 0; i < selections.length; i++) {
		var id = prefix + "_" + selections[i] + "_box";
		var elem = document.getElementById(id);
		if (elem)
			elem.checked = false;
	}
	selections.splice(0, selections.length);
}

function move_guests_to_table(table) {
	var modified_groups = [];
	for (var i = 0; i < unassigned_guests_selected.length; i++) {
		var guest_num = unassigned_guests_selected[i];
		var guest = guests[guest_num - 1];
		guest.table_num = table.table_num;
		// Remove the guest from the original group.
		var group = groups[guest.group_num - 1];
		update_set(group.guest_nums, guest_num, false);
		update_set(modified_groups, guest.group_num, true);
		// Add the guest to the new table.
		update_set(table.guest_nums, guest_num, true);
	}
	// Re-render the affected groups.
	for (var i = 0; i < modified_groups.length; i++) {
		var group_num = modified_groups[i];
		var group = groups[group_num - 1];
		var elem = group.group_elem;
		var parent = elem.parentNode;
		parent.removeChild(elem);
		add_group(group);
	}
}

function do_newtable() {
	if (unassigned_guests_selected.length < 1) {
		alert("Please select one or more guests from the left column.")
		return false;
	}
	var new_table_num = tables.length + 1;
	var new_seating_prefs = "";
	if (groups_selected.length > 0) {
		var names = [];
		var prefs = [];
		for (var i = 0; i < groups_selected.length; i++) {
			var group_num = groups_selected[i];
			if (groups[group_num - 1].seating_prefs != "")
				prefs.push(groups[group_num - 1].seating_prefs);
		}
		new_seating_prefs = prefs.join('/');
	}
	var new_table = {
		table_num: new_table_num,
		seating_prefs: new_seating_prefs,
		checked: false,
		guest_nums: []
	};
	tables.push(new_table);
	move_guests_to_table(new_table);
	// Render the new table.
	add_table(new_table, table_div, null);
	clear_selections('guest', unassigned_guests_selected);
	clear_selections('guest', assigned_guests_selected);
	clear_selections('group', groups_selected);
	clear_selections('table', tables_selected);
	mark_dirty();
	return false;
}

function do_move() {
	if (tables_selected.length != 1) {
		alert("Please select one table, or click \u201cNew Table.\u201d")
		return false;
	}
	var table_num = tables_selected[0];
	var table = tables[table_num - 1];
	if (unassigned_guests_selected.length < 1) {
		alert("Please select one or more guests from the left column.");
		return false;
	}
	move_guests_to_table(table);
	// Re-render the modified table.
	var old = table.table_elem;
	var parent = old.parentNode;
	add_table(table, parent, old);
	clear_selections('guest', unassigned_guests_selected);
	clear_selections('guest', assigned_guests_selected);
	clear_selections('group', groups_selected);
	clear_selections('table', tables_selected);
	mark_dirty();
	return false;
}

function do_remove() {
	if (assigned_guests_selected.length == 0) {
		alert("Please select one or more guests from the right column.");
		return false;
	}
	var modified_groups = [];
	var modified_tables = [];
	for (var i = 0; i < assigned_guests_selected.length; i++) {
		var guest_num = assigned_guests_selected[i];
		var guest = guests[guest_num - 1];
		var group = groups[guest.group_num - 1];
		var table = tables[guest.table_num - 1];
		update_set(group.guest_nums, guest_num, true);
		update_set(table.guest_nums, guest_num, false);
		update_set(modified_groups, guest.group_num, true);
		update_set(modified_tables, guest.table_num, true);
		guest.table_num = 0;
	}
	// Re-render the affected groups.
	for (var i = 0; i < modified_groups.length; i++) {
		var group_num = modified_groups[i];
		var group = groups[group_num - 1];
		var elem = group.group_elem;
		if (elem) {
			var parent = elem.parentNode;
			parent.removeChild(elem);
		}
		add_group(group);
	}
	// Re-render the affected tables.
	for (var i = 0; i < modified_tables.length; i++) {
		var table_num = modified_tables[i];
		var table = tables[table_num - 1];
		var elem = table.table_elem;
		var parent = elem.parentNode;
		add_table(table, parent, elem);
	}
	clear_selections('guest', unassigned_guests_selected);
	clear_selections('guest', assigned_guests_selected);
	clear_selections('group', groups_selected);
	clear_selections('table', tables_selected);
	mark_dirty();
	return false;
}

function do_save() {
	var guests_json = document.getElementById("guests_json");
	var guest_properties = [
		"key", "is_golfer", "guest_num", "table_num", "orig_table_num", "guest_name"
	];
	guests_json.value = JSON.stringify(guests, guest_properties);
	var form = document.getElementById("form");
	if (form)
		form.submit();
	
	mark_clean();
	return false;
}
