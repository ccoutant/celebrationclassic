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
	var sponsorship_choices = document.getElementById("sponsorship_choices");
	var go_campaign_div = document.getElementById("go_campaign");
	var checkboxes = sponsorship_choices.getElementsByTagName("input");
	var show_sponsorships_box = document.getElementById("checkbox_show_sponsorships");
	var show_go_campaign_box = document.getElementById("checkbox_show_go_campaign");
	var angel = document.getElementById("angel");
	var angelbox = angel.getElementsByTagName("input")[0];
	var otherbox = document.getElementById("entry_other");
	var golferbox = document.getElementById("entry_num_golfers");
	var go_golferbox = document.getElementById("entry_go_golfers");
	var dinnerbox = document.getElementById("entry_num_dinners");
	var includes_span = document.getElementById("included_text");
	var sponsor_agree_div = document.getElementById("sponsor_agree");
	var agreebox = document.getElementById("entry_agree");
	var printednamesbox = document.getElementById("entry_printednames");
	var totalbox = document.getElementById("entry_payment_due");
	var totalbox_c = document.getElementById("entry_payment_due_c");
	var creditbox = document.getElementById("entry_credits");
	var creditbox_c = document.getElementById("entry_credits_c");
	var netbox = document.getElementById("entry_net_payment_due");
	var netbox_c = document.getElementById("entry_net_payment_due_c");

	var early_bird = parseInt(document.getElementById("early_bird").value);
	var golf_price_early = document.getElementById("golf_price_early").value;
	var golf_price_late = document.getElementById("golf_price_late").value;
	var dinner_price_early = document.getElementById("dinner_price_early").value;
	var dinner_price_late = document.getElementById("dinner_price_late").value;
	var golf_price = early_bird ? golf_price_early : golf_price_late;
	var dinner_price = early_bird ? dinner_price_early : dinner_price_late;

	// Show or hide the sponsorship checkboxes.
	if (show_sponsorships_box.checked)
		sponsorship_choices.style.display = "block";
	else {
		sponsorship_choices.style.display = "none";
		for (var i = 0; i < checkboxes.length; i++)
			checkboxes[i].checked = false;
	}

	// Show or hide the GO campaign box.
	if (show_go_campaign_box.checked)
		go_campaign_div.style.display = "block";
	else
		go_campaign_div.style.display = "none";

	// The discount code can represent either a number of golfers or the value
	// of a sponsorship.
	var go_discount = parseInt(go_golferbox.value);
	var go_golfers = 0;
	if (go_discount <= 12) {
		go_golfers = go_discount;
		go_discount = 0;
	}

	// Calculate total cost of sponsorships and number of golfers/dinners included.
	var total = 0;
	var golfers_included = 0;
	var dinners_included = 0;
	for (var i = 0; i < checkboxes.length; i++) {
		if (checkboxes[i].checked) {
			var tuple = checkboxes[i].value.split(":");
			var price = parseInt(tuple[2]);
			var included = parseInt(tuple[3]);
			total += price;
			golfers_included += included;
		}
	}
	dinners_included = golfers_included;

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
		var tuple = angelbox.value.split(":");
		var price = parseInt(tuple[2]);
		var included = parseInt(tuple[3]);
		if (price != go_discount)
			total += price;
		golfers_included += included;
		dinners_included += included;
	}

	// If no sponsorship, hide the "agree to publish my name" checkbox.
	if (total > 0)
		sponsor_agree_div.style.display = "block";
	else
		sponsor_agree_div.style.display = "none";

	golfers_included += go_golfers;

	// Calculate price for additional golfers and dinners.
	golfers -= golfers_included;
	if (golfers < 0) {
		// Transfer unused golfer allowance to dinner allowance.
		dinners_included -= golfers;
		golfers = 0;
		}
	total += golfers * golf_price;
	var dinners = parseInt(dinnerbox.value) - dinners_included;
	if (dinners < 0)
		dinners = 0;
	total += dinners * dinner_price;

	if (otherbox.value) {
		var otherval = parseInt(otherbox.value);
		if (!isNaN(otherval))
			total += parseInt(otherbox.value);
	}

	totalbox.value = total;
	totalbox_c.value = add_commas(total);
	credits = parseInt(creditbox.value);
	creditbox_c.value = add_commas(credits);
	netdue = total - credits < 0 ? 0 : total - credits;
	netbox.value = netdue;
	netbox_c.value = add_commas(netdue);
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
	var show_go_campaign_box = document.getElementById("checkbox_show_go_campaign");
	show_go_campaign_box.onchange = recalculate;
}
