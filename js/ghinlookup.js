function initialize() {
	var page_offset = parseInt(document.getElementById('this_page_offset').value, 10);
	var count = parseInt(document.getElementById('count').value, 10);
	for (i = page_offset; i < page_offset + count; i++) {
		var ghin_box = document.getElementById('ghin_' + i);
		if (ghin_box.value != "")
			insert_lookup_button(i);
		else
			ghin_box.onchange = ghin_onchange_handler(i);
	}
}

function ghin_onchange_handler(i) {
	return function() {
		insert_lookup_button(i);
	};
}

function insert_lookup_button(i) {
	var button_cell = document.getElementById('button_' + i);
	if (button_cell.firstChild != null)
		return;
	var button = document.createElement('button');
	button.title = "Lookup index by GHIN number";
	button.appendChild(document.createTextNode('\u21d2'));
	button_cell.appendChild(button);
	button.onclick = lookup_button_handler(i);
}

function lookup_button_handler(i) {
	return function() {
		var ghin_box = document.getElementById('ghin_' + i);
		var xhr = new XMLHttpRequest();
		xhr.onreadystatechange = function() {
			if (xhr.readyState == XMLHttpRequest.DONE) {
				json = JSON.parse(this.responseText);
				show_popup(i, json);
			}
		}
		xhr.open('GET', '/ghin-lookup/' + ghin_box.value, true);
		xhr.send();
		return false;
	}
}

function Point(x, y) {
	this.x = x;
	this.y = y;
	return this;
}

function getPosition(elem) {
	var x = 0;
	var y = 0;
	while (elem) {
		x += elem.offsetLeft;
		y += elem.offsetTop;
		elem = elem.offsetParent;
	}
	return new Point(x, y);
}

function show_popup(i, json) {
	var name = json['name'];
	var ghin = json['ghin'];
	var rows = json['rows'];
	if (name == "" || ghin == "" || rows.length == 0) {
		show_empty_results(i);
		return;
	}
	var container = document.getElementById('container');
	var button_cell = document.getElementById('button_' + i);
	var container_pos = getPosition(container);
	var button_pos = getPosition(button_cell);
	var popup = document.createElement('div');
	popup.className = "popup";
	popup.style.left = (button_pos.x - container_pos.x) + 'px';
	popup.style.top = (button_pos.y + button_cell.offsetHeight - container_pos.y) + 'px';
	var closebox = document.createElement('div');
	closebox.className = "closebox";
	closebox.appendChild(document.createTextNode('\u2715\ufe0e'));
	closebox.onclick = function() {
		container.removeChild(popup);
	};
	popup.appendChild(closebox);
	var p = document.createElement('p');
	p.appendChild(document.createTextNode(name + ' (' + ghin + ')'));
	popup.appendChild(p);
	var tbl = document.createElement('table');
	var thead = document.createElement('thead');
	var tr = document.createElement('tr');
	var th = document.createElement('th');
	th.appendChild(document.createTextNode('Club'));
	tr.appendChild(th);
	th = document.createElement('th');
	th.appendChild(document.createTextNode('Index'));
	tr.appendChild(th);
	th = document.createElement('th');
	th.appendChild(document.createTextNode('Eff. Date'));
	tr.appendChild(th);
	thead.appendChild(tr);
	tbl.appendChild(thead);
	var tbody = document.createElement('tbody');
	for (j = 0; j < rows.length; j++) {
		var row = rows[j];
		var tr = document.createElement('tr');
		var td = document.createElement('td');
		td.appendChild(document.createTextNode(row[0]));
		tr.appendChild(td);
		td = document.createElement('td');
		var a = document.createElement('a');
		a.title = "Use this index";
		a.appendChild(document.createTextNode(row[1]));
		a.onclick = index_click_handler(i, row[1], container, popup);
		td.appendChild(a);
		tr.appendChild(td);
		td = document.createElement('td');
		td.appendChild(document.createTextNode(row[2]));
		tr.appendChild(td);
		tbody.appendChild(tr);
	}
	tbl.appendChild(tbody);
	popup.appendChild(tbl);
	container.appendChild(popup);
}

function index_click_handler(i, index, container, popup) {
	return function() {
		var index_cell = document.getElementById('index_' + i);
		index_cell.value = index;
		container.removeChild(popup);
		return false;
	};
}

function show_empty_results(i) {
	var ghin_box = document.getElementById('ghin_' + i);
	var container = document.getElementById('container');
	var button_cell = document.getElementById('button_' + i);
	var container_pos = getPosition(container);
	var button_pos = getPosition(button_cell);
	var popup = document.createElement('div');
	popup.className = "popup";
	popup.style.left = (button_pos.x - container_pos.x) + 'px';
	popup.style.top = (button_pos.y + button_cell.offsetHeight - container_pos.y) + 'px';
	var closebox = document.createElement('div');
	closebox.className = "closebox";
	closebox.appendChild(document.createTextNode('\u2715\ufe0e'));
	closebox.onclick = function() {
		container.removeChild(popup);
	};
	popup.appendChild(closebox);
	var p = document.createElement('p');
	p.appendChild(document.createTextNode("No results for GHIN number " + ghin_box.value + '.'));
	popup.appendChild(p);
	container.appendChild(popup);
}