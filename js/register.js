function add_commas(str) {
    str += '';
    v = str.split('.');
    v1 = v[0];
    v2 = v.length > 1 ? '.' + v[1] : '';
    var re = /(\d+)(\d{3})/;
    while (re.test(v1)) {
        v1 = v1.replace(re, '$1' + ',' + '$2');
    }
    return v1 + v2;
}

function recalculate() {
	var sponsorships = document.getElementById("sponsorships");
	var checkboxes = sponsorships.getElementsByTagName("input");
	var angel = document.getElementById("angel");
	var angelbox = angel.getElementsByTagName("input")[0];
	var otherbox = document.getElementById("entry_other");
	var golferbox = document.getElementById("entry_num_golfers");
	var dinnerbox = document.getElementById("entry_num_dinners");
	var includes_span = document.getElementById("included_text");
	var agreebox = document.getElementById("entry_agree");
	var printednamesbox = document.getElementById("entry_printednames");
	var totalbox = document.getElementById("entry_payment_due");
	var totalbox_c = document.getElementById("entry_payment_due_c");

	// Calculate total cost of sponsorships and number of golfers/dinners included.
	var total = 0;
	var golfers_included = 0;
	var dinners_included = 0;
	for (var i = 0; i < checkboxes.length; i++) {
		if (checkboxes[i].checked) {
			var triple = checkboxes[i].value.split(":");
			var price = parseInt(triple[2]);
			total += price;
			if (price >= 20000)
				golfers_included += 12;
			else if (price >= 15000)
				golfers_included += 8;
			else if (price >= 10000)
				golfers_included += 6;
			else if (price >= 3000)
				golfers_included += 2;
			else
				golfers_included += 1;
		}
	}
	dinners_included = golfers_included;
	if (otherbox.value)
		total += parseInt(otherbox.value);

	// Insert explanation of included golfers and dinners.
	var includes = "";
	if (golfers_included == 1)
		includes = "Your sponsorship includes 1 golfer";
	else if (golfers_included > 1)
		includes = "Your sponsorship includes " + golfers_included + " golfers";
	if (dinners_included == 1)
		includes += " plus 1 additional dinner guest.";
	else if (dinners_included > 1)
		includes += " plus " + dinners_included + " additional dinner guests.";
	if (includes_span)
		includes_span.innerHTML = includes;

	// Adjust the selectors for number of golfers and dinner guests.
	adjust_selector(golferbox, golfers_included);
	adjust_selector(dinnerbox, dinners_included);

	// Offer Angel sponsorship for foursomes.
	var golfers = parseInt(golferbox.value);
	if (golfers_included == 0 && golfers >= 4)
		angel.style.display = "block";
	else {
		angel.style.display = "none";
		angelbox.checked = false;
	}
	if (angelbox.checked) {
		total += 3000;
		golfers_included += 4;
		dinners_included += 4;
	}

	// If no sponsorship, disable the "agree to publish my name" checkbox.
	agreebox.disabled = total == 0;
	printednamesbox.disabled = total == 0 || !agreebox.checked;

	// Calculate price for additional golfers and dinners.
	golfers -= golfers_included;
	if (golfers < 0) {
		// Transfer unused golfer allowance to dinner allowance.
		dinners_included -= golfers;
		golfers = 0;
		}
	total += golfers * 360;
	var dinners = parseInt(dinnerbox.value) - dinners_included;
	if (dinners < 0)
		dinners = 0;
	total += dinners * 75;
	totalbox.value = total;
	totalbox_c.value = add_commas(total);
}

function adjust_selector(e, n) {
	if (n < 4)
		n = 4;
	var options = e.getElementsByTagName("option");
	var len = options.length;
	for (var i = len - 1; i > n; i--)
		e.removeChild(options[i]);
	for (var i = options.length; i < n + 1; i++) {
		var o = document.createElement("option");
		o.label = "" + i;
		o.value = o.label;
		var t = document.createTextNode(o.value);
		o.appendChild(t);
		e.appendChild(o);
	}
}

function ignore_enter(e) {
	e = e || event;
	var key = e.keyCode || event.which || event.charCode;
	if( key == 13 ) {
		e.cancelBubble = true;
		e.returnValue = false;
		if (e.stopPropagation) {
			e.stopPropagation();
			e.preventDefault();
		}
		this.blur();
	}
}

function install_recalculate_hooks() {
	var sponsorships = document.getElementById("sponsorships");
	var checkboxes = sponsorships.getElementsByTagName("input");
	var angel = document.getElementById("angel");
	var angelbox = angel.getElementsByTagName("input")[0];
	for (var i = 0; i < checkboxes.length; i++) {
		checkboxes[i].onclick = recalculate;
	}
	angelbox.onclick = recalculate;
	var otherbox = document.getElementById("entry_other");
	otherbox.onchange = recalculate;
	otherbox.onkeypress = ignore_enter;
	var agreebox = document.getElementById("entry_agree");
	agreebox.onclick = recalculate;
	var printednamesbox = document.getElementById("entry_printednames");
	printednamesbox.onkeypress = ignore_enter;
	var selectbox = document.getElementById("entry_num_golfers");
	selectbox.onchange = recalculate;
	selectbox = document.getElementById("entry_num_dinners");
	selectbox.onchange = recalculate;
}
