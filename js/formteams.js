function initialize() {
	group_divs = [
		document.getElementById('singles'),
		document.getElementById('twosomes'),
		document.getElementById('threesomes'),
		document.getElementById('foursomes')
	];
	team_div = document.getElementById('teams');
	for (var i = 0; i < groups.length; i++) {
		add_group(groups[i]);
	}
	for (var i = 0; i < teams.length; i++) {
		add_team(teams[i], team_div, null);
	}
	mark_clean();
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

function top_onchange_handler(topbox, subboxes, group_num, team_num) {
	return function() {
		var is_checked = topbox.checked;
		for (var i = 0; i < subboxes.length; i++) {
			var golfer_num = parseInt(subboxes[i].value);
			subboxes[i].checked = is_checked;
			if (team_num > 0)
				update_set(assigned_golfers_selected, golfer_num, is_checked);
			else if (group_num > 0)
				update_set(unassigned_golfers_selected, golfer_num, is_checked);
		}
		if (team_num > 0) {
			update_set(teams_selected, team_num, is_checked);
		} else if (group_num > 0) {
			update_set(groups_selected, group_num, is_checked);
		}
	}
}

function sub_onchange_handler(topbox, subboxes, group_num, team_num, n) {
	return function() {
		var num_checked = 0;
		var golfer_num = parseInt(subboxes[n].value);
		var is_checked = subboxes[n].checked;
		if (team_num > 0)
			update_set(assigned_golfers_selected, golfer_num, is_checked);
		else if (group_num > 0)
			update_set(unassigned_golfers_selected, golfer_num, is_checked);
		for (var i = 0; i < subboxes.length; i++) {
			if (subboxes[i].checked)
				num_checked++;
		}
		if (num_checked == subboxes.length) {
			topbox.checked = true;
			if (team_num > 0) {
				update_set(teams_selected, team_num, true);
			} else if (group_num > 0) {
				update_set(groups_selected, group_num, true);
			}
		} else if (num_checked == 0) {
			topbox.checked = false;
			if (team_num > 0) {
				update_set(teams_selected, team_num, false);
			} else if (group_num > 0) {
				update_set(groups_selected, group_num, false);
			}
		}
	}
}

function radio_onclick_handler(thiscartbuttons, othercartbuttons, n) {
	return function() {
		var vals = thiscartbuttons[n].value.split(":");
		var golfer_num = parseInt(vals[0]);
		var cart = parseInt(vals[1]);
		golfers[golfer_num - 1].cart = cart;
		var found = 0;
		for (var i = 1; i < thiscartbuttons.length; i++) {
			var j = n - i;
			if (j < 0)
				j += thiscartbuttons.length;
			if (thiscartbuttons[j].checked) {
				found++;
				if (found > 1) {
					vals = othercartbuttons[j].value.split(":");
					golfer_num = parseInt(vals[0]);
					cart = parseInt(vals[1]);
					golfers[golfer_num - 1].cart = cart;
					othercartbuttons[j].checked = true;
					break;
				}
			}
		}
		mark_dirty();
		return true;
	}
}

function install_checkbox_handlers(topbox, subboxes, group_num, team_num) {
	topbox.onchange = top_onchange_handler(topbox, subboxes, group_num, team_num);
	for (var i = 0; i < subboxes.length; i++) {
		subboxes[i].onchange = sub_onchange_handler(topbox, subboxes, group_num, team_num, i);
	}
}

function install_radio_handlers(cart1buttons, cart2buttons) {
	for (var i = 0; i < cart1buttons.length; i++) {
		cart1buttons[i].onclick = radio_onclick_handler(cart1buttons, cart2buttons, i);
		cart2buttons[i].onclick = radio_onclick_handler(cart2buttons, cart1buttons, i);
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
	for (var i = 0; i < group.golfer_nums.length; i++) {
		var golfer_num = group.golfer_nums[i];
		var golfer = golfers[golfer_num - 1];
		var li = document.createElement("li");

		var subbox = document.createElement("input");
		subbox.setAttribute("id", "golfer_" + golfer.golfer_num + "_box");
		subbox.setAttribute("class", "golfer_checkbox");
		subbox.setAttribute("type", "checkbox");
		subbox.setAttribute("name", "unassigned_golfers_selected");
		subbox.setAttribute("value", golfer.golfer_num.toString());
		li.appendChild(subbox);
		subboxes.push(subbox);

		li.appendChild(document.createTextNode(" "));

		label = document.createElement("label");
		label.setAttribute("for", "golfer_" + golfer.golfer_num + "_box");
		name = document.createElement("span");
		name.setAttribute("class", "golfername");
		name.appendChild(document.createTextNode(golfer.golfer_name));
		label.appendChild(name);
		li.appendChild(label);

		var hdcp = document.createElement("span");
		hdcp.setAttribute("class", "handicap");
		hdcp.appendChild(document.createTextNode("(" + golfer.course_handicap + ")"));
		li.appendChild(hdcp);

		ul.appendChild(li);
	}
	div.appendChild(ul);

	if (group.pairing_prefs != "") {
		var pairing = document.createElement("p");
		pairing.setAttribute("class", "pairing");
		pairing.appendChild(document.createTextNode("Pairing preference: " + group.pairing_prefs));
		div.appendChild(pairing);
	}

	install_checkbox_handlers(topbox, subboxes, group.group_num, 0);
	return div;
}

function add_group(group) {
	if (group.golfer_nums.length == 0) {
		group.group_elem = null;
		return;
	}
	var group_size = Math.min(4, group.golfer_nums.length);
	var group_div = group_divs[group_size - 1];
	var elem = make_group(group);
	// Find next group in the same div.
	var next = null;
	for (var i = group.group_num; i < groups.length; i++) {
		if (groups[i].golfer_nums.length == group.golfer_nums.length) {
			next = groups[i].group_elem;
			break;
		}
	}
	if (next)
		group_div.insertBefore(elem, next);
	else
		group_div.appendChild(elem);
	group.group_elem = elem;
}

function make_team(team) {
	var div = document.createElement("div");
	div.setAttribute("class", "team");

	var contact = document.createElement("p");
	contact.setAttribute("class", "contact");
	var topbox = document.createElement("input");
	topbox.setAttribute("id", "team_" + team.team_num + "_box");
	topbox.setAttribute("class", "team_checkbox");
	topbox.setAttribute("type", "checkbox");
	topbox.setAttribute("name", "teams_selected");
	topbox.setAttribute("value", team.team_num.toString());
	contact.appendChild(topbox);
	contact.appendChild(document.createTextNode(" "));
	var label = document.createElement("label");
	label.setAttribute("for", "team_" + team.team_num + "_box");
	var name = document.createTextNode("Team " + team.team_num);
	label.appendChild(name);
	contact.appendChild(label);
	contact.appendChild(document.createTextNode(" "));
	var namebox = document.createElement("input");
	namebox.setAttribute("id", "team_" + team.team_num + "_name");
	namebox.setAttribute("type", "text");
	namebox.setAttribute("size", "20");
	namebox.setAttribute("name", "team_" + team.team_num + "_name");
	namebox.setAttribute("value", team.name);
	contact.appendChild(namebox);
	namebox.oninput = mark_dirty;
	div.appendChild(contact);

	var subboxes = []
	var cart1buttons = []
	var cart2buttons = []
	var ul = document.createElement("ul");
	for (var i = 0; i < team.golfer_nums.length; i++) {
		var golfer_num = team.golfer_nums[i];
		var golfer = golfers[golfer_num - 1];
		var li = document.createElement("li");

		var subbox = document.createElement("input");
		subbox.setAttribute("id", "golfer_" + golfer.golfer_num + "_box");
		subbox.setAttribute("class", "golfer_checkbox");
		subbox.setAttribute("type", "checkbox");
		subbox.setAttribute("name", "assigned_golfers_selected");
		subbox.setAttribute("value", golfer.golfer_num.toString());
		li.appendChild(subbox);
		subboxes.push(subbox);

		li.appendChild(document.createTextNode(" "));

		label = document.createElement("label");
		label.setAttribute("for", "golfer_" + golfer.golfer_num + "_box");
		name = document.createElement("span");
		name.setAttribute("class", "golfername");
		name.appendChild(document.createTextNode(golfer.golfer_name));
		label.appendChild(name);
		li.appendChild(label);

		var hdcp = document.createElement("span");
		hdcp.setAttribute("class", "handicap");
		hdcp.appendChild(document.createTextNode("(" + golfer.course_handicap + ")"));
		li.appendChild(hdcp);
		var cart = document.createElement("span");
		cart.setAttribute("class", "cart");
		label = document.createElement("label");
		label.setAttribute("for", "golfer_" + golfer.golfer_num + "_cart1");
		label.appendChild(document.createTextNode("Cart 1"));
		cart.appendChild(label);
		cart.appendChild(document.createTextNode(" "));
		var cartradio = document.createElement("input");
		cartradio.setAttribute("id", "golfer_" + golfer.golfer_num + "_cart1");
		cartradio.setAttribute("name", "golfer_" + golfer.golfer_num + "_cart");
		cartradio.setAttribute("type", "radio");
		cartradio.setAttribute("value", golfer.golfer_num.toString() + ":1");
		if (golfer.cart == 1)
			cartradio.checked = true;
		cart.appendChild(cartradio);
		cart1buttons.push(cartradio);
		cart.appendChild(document.createTextNode(" "));
		label = document.createElement("label");
		label.setAttribute("for", "golfer_" + golfer.golfer_num + "_cart2");
		label.appendChild(document.createTextNode("2"));
		cart.appendChild(label);
		cart.appendChild(document.createTextNode(" "));
		cartradio = document.createElement("input");
		cartradio.setAttribute("id", "golfer_" + golfer.golfer_num + "_cart2");
		cartradio.setAttribute("name", "golfer_" + golfer.golfer_num + "_cart");
		cartradio.setAttribute("type", "radio");
		cartradio.setAttribute("value", golfer.golfer_num.toString() + ":2");
		if (golfer.cart == 2)
			cartradio.checked = true;
		cart.appendChild(cartradio);
		cart2buttons.push(cartradio);
		li.appendChild(cart);

		ul.appendChild(li);
	}
	for (var i = team.golfer_nums.length; i < 4; i++) {
		var li = document.createElement("li");

		var subbox = document.createElement("input");
		subbox.setAttribute("class", "golfer_checkbox");
		subbox.setAttribute("type", "checkbox");
		subbox.setAttribute("value", "0");
		subbox.setAttribute("disabled", true);
		li.appendChild(subbox);

		li.appendChild(document.createTextNode(" "));

		name = document.createElement("span");
		name.setAttribute("class", "placeholder");
		name.appendChild(document.createTextNode("\xa0"));
		li.appendChild(name);

		ul.appendChild(li);
	}
	div.appendChild(ul);

	if (team.pairing_prefs != "") {
		var pairing = document.createElement("p");
		pairing.setAttribute("class", "pairing");
		pairing.appendChild(document.createTextNode("Pairing preference: " + team.pairing_prefs));
		div.appendChild(pairing);
	}

	install_checkbox_handlers(topbox, subboxes, 0, team.team_num);
	install_radio_handlers(cart1buttons, cart2buttons);
	return div;
}

function add_team(team, parent, replace) {
	var elem = make_team(team);
	var before = null;
	if (replace) {
		before = replace.nextSibling;
		parent.removeChild(replace);
	}
	if (before)
		parent.insertBefore(elem, before);
	else
		parent.appendChild(elem);
	team.team_elem = elem;
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

function move_golfers_to_team(team) {
	var modified_groups = [];
	var cart_1_count = 0;
	for (var i = 0; i < team.golfer_nums.length; i++) {
		var golfer_num = team.golfer_nums[i];
		if (golfers[golfer_num - 1].cart == 1)
			cart_1_count++;
	}
	for (var i = 0; i < unassigned_golfers_selected.length; i++) {
		var golfer_num = unassigned_golfers_selected[i];
		var golfer = golfers[golfer_num - 1];
		golfer.team_num = team.team_num;
		golfer.cart = (cart_1_count < 2 ? 1 : 2);
		cart_1_count++;
		// Remove the golfer from the original group.
		var group = groups[golfer.group_num - 1];
		update_set(group.golfer_nums, golfer_num, false);
		update_set(modified_groups, golfer.group_num, true);
		// Add the golfer to the new team.
		update_set(team.golfer_nums, golfer_num, true);
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

function update_team_names() {
	for (var i = 0; i < teams.length; i++) {
		var team = teams[i];
		var name_field = document.getElementById("team_" + team.team_num + "_name");
		team.name = name_field.value;
	}
}

function do_newteam() {
	if (unassigned_golfers_selected.length < 1) {
		alert("Please select up to four golfers from the left column.")
		return false;
	}
	if (unassigned_golfers_selected.length > 4) {
		alert("Please select no more than four golfers.")
		return false;
	}
	var new_team_num = teams.length + 1;
	var new_team_name = "";
	var new_pairing_prefs = "";
	if (groups_selected.length > 0) {
		var names = [];
		var prefs = [];
		for (var i = 0; i < groups_selected.length; i++) {
			var group_num = groups_selected[i];
			names.push(groups[group_num - 1].last_name);
			if (groups[group_num - 1].pairing_prefs != "")
				prefs.push(groups[group_num - 1].pairing_prefs);
		}
		new_team_name = names.join('/');
		new_pairing_prefs = prefs.join('/');
	}
	var new_team = {
		team_num: new_team_num,
		key: '',
		name: new_team_name,
		pairing_prefs: new_pairing_prefs,
		checked: false,
		golfer_nums: []
	};
	teams.push(new_team);
	move_golfers_to_team(new_team);
	// Render the new team.
	add_team(new_team, team_div, null);
	clear_selections('golfer', unassigned_golfers_selected);
	clear_selections('golfer', assigned_golfers_selected);
	clear_selections('group', groups_selected);
	clear_selections('team', teams_selected);
	mark_dirty();
	return false;
}

function do_move() {
	if (teams_selected.length != 1) {
		alert("Please select one team, or click \u201cNew Team.\u201d")
		return false;
	}
	var team_num = teams_selected[0];
	var team = teams[team_num - 1];
	var available = 4 - team.golfer_nums.length;
	if (available <= 0) {
		alert("The selected team is full. Please select a different team, or click \u201cNew Team.\u201d");
		return false;
	} else if (available == 1 && unassigned_golfers_selected.length != 1) {
		alert("Please select one golfer from the left column.");
		return false;
	} else if (unassigned_golfers_selected.length < 1) {
		alert("Please select up to " + available + " golfers from the left column.");
		return false;
	} else if (unassigned_golfers_selected.length > available) {
		alert("Please select no more than " + available + " golfers from the left column.");
		return false;
	}
	move_golfers_to_team(team);
	update_team_names();
	// Re-render the modified team.
	var old = team.team_elem;
	var parent = old.parentNode;
	add_team(team, parent, old);
	clear_selections('golfer', unassigned_golfers_selected);
	clear_selections('golfer', assigned_golfers_selected);
	clear_selections('group', groups_selected);
	clear_selections('team', teams_selected);
	mark_dirty();
	return false;
}

function do_remove() {
	if (assigned_golfers_selected.length == 0) {
		alert("Please select one or more golfers from the right column.");
		return false;
	}
	var modified_groups = [];
	var modified_teams = [];
	for (var i = 0; i < assigned_golfers_selected.length; i++) {
		var golfer_num = assigned_golfers_selected[i];
		var golfer = golfers[golfer_num - 1];
		var group = groups[golfer.group_num - 1];
		var team = teams[golfer.team_num - 1];
		update_set(group.golfer_nums, golfer_num, true);
		update_set(team.golfer_nums, golfer_num, false);
		update_set(modified_groups, golfer.group_num, true);
		update_set(modified_teams, golfer.team_num, true);
		golfer.team_num = 0;
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
	// Re-render the affected teams.
	update_team_names();
	for (var i = 0; i < modified_teams.length; i++) {
		var team_num = modified_teams[i];
		var team = teams[team_num - 1];
		var elem = team.team_elem;
		var parent = elem.parentNode;
		add_team(team, parent, elem);
	}
	clear_selections('golfer', unassigned_golfers_selected);
	clear_selections('golfer', assigned_golfers_selected);
	clear_selections('group', groups_selected);
	clear_selections('team', teams_selected);
	mark_dirty();
	return false;
}

function do_save() {
	update_team_names();
	var groups_json = document.getElementById("groups_json");
	var teams_json = document.getElementById("teams_json");
	var golfers_json = document.getElementById("golfers_json");
	var group_properties = [
		"group_num", "key", "id", "first_name", "last_name",
		"pairing_prefs", "golfer_nums"
	];
	var team_properties = [
		"team_num", "key", "name", "pairing_prefs", "golfer_nums"
	];
	var golfer_properties = [
		"golfer_num", "key", "golfer_name", "group_num",
		"team_num", "course_handicap", "cart", "md5"
	];
	groups_json.value = JSON.stringify(groups, group_properties);
	teams_json.value = JSON.stringify(teams, team_properties);
	golfers_json.value = JSON.stringify(golfers, golfer_properties);
	console.log("save");
	console.log("teams_json = " + teams_json.value);
	var form = document.getElementById("form");
	if (form)
		form.submit();
	
	mark_clean();
	return false;
}
