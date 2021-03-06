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
	var go_campaign_div_2 = document.getElementById("go_campaign_no_code");
	var checkboxes = sponsorship_choices.getElementsByTagName("input");
	var show_sponsorships_box = document.getElementById("checkbox_show_sponsorships");
	var show_go_campaign_box = document.getElementById("checkbox_show_go_campaign");
	var angel = document.getElementById("angel");
	var angelbox = angel.getElementsByTagName("input")[0];
	var otherbox = document.getElementById("entry_other");
	var golferbox = document.getElementById("entry_num_golfers");
	var golferonlybox = document.getElementById("entry_num_golfers_no_dinner");
	var use_go_discount_code_box = document.getElementById("entry_use_go_discount_code");
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

	var admin_user = parseInt(document.getElementById("admin_user").value);
	var golf_sold_out = parseInt(document.getElementById("golf_sold_out").value);
	var dinner_sold_out = parseInt(document.getElementById("dinner_sold_out").value);
	var golf_early_bird = parseInt(document.getElementById("early_bird").value);
	var dinner_early_bird = parseInt(document.getElementById("dinner_early_bird").value);
	var golf_price_early = document.getElementById("golf_price_early").value;
	var golf_price_late = document.getElementById("golf_price_late").value;
	var golf_only_price_early = document.getElementById("golf_only_price_early").value;
	var golf_only_price_late = document.getElementById("golf_only_price_late").value;
	var dinner_price_early = document.getElementById("dinner_price_early").value;
	var dinner_price_late = document.getElementById("dinner_price_late").value;
	var golf_price = golf_early_bird ? golf_price_early : golf_price_late;
	var golf_only_price = golf_early_bird ? golf_only_price_early : golf_only_price_late;
	var dinner_price = dinner_early_bird ? dinner_price_early : dinner_price_late;

	// Show or hide the sponsorship checkboxes.
	if (show_sponsorships_box.checked)
		sponsorship_choices.style.display = "block";
	else {
		sponsorship_choices.style.display = "none";
		for (var i = 0; i < checkboxes.length; i++)
			checkboxes[i].checked = false;
	}

	// Show or hide the GO campaign box.
	var use_go_discount_code = parseInt(use_go_discount_code_box.value);
	if (show_go_campaign_box.checked && use_go_discount_code)
		go_campaign_div.style.display = "block";
	else
		go_campaign_div.style.display = "none";
	if (show_go_campaign_box.checked && !use_go_discount_code)
		go_campaign_div_2.style.display = "block";
	else
		go_campaign_div_2.style.display = "none";

	// The discount code can represent either a number of golfers or the value
	// of a sponsorship.
	var go_discount = 0;
	var go_golfers = 0;
	if (use_go_discount_code) {
		go_discount = parseInt(go_golferbox.value);
		go_golfers = 0;
		if (go_discount <= 12) {
			go_golfers = go_discount;
			go_discount = 0;
		}
	} else {
		go_golfers = (show_go_campaign_box.checked ? 2 : 0);
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
	adjust_selector(golferbox, Math.max(golfers_included, parseInt(golferbox.value)), (golf_sold_out || dinner_sold_out) && !admin_user);
	if (golferonlybox)
		adjust_selector(golferonlybox, Math.max(golfers_included, parseInt(golferonlybox.value)), golf_sold_out && !admin_user);
	adjust_selector(dinnerbox, Math.max(dinners_included, parseInt(dinnerbox.value)), dinner_sold_out && !admin_user);

	// Offer Angel sponsorship for foursomes.
	var golfers = parseInt(golferbox.value);
	var golfers_no_dinner = 0;
	if (golferonlybox)
		golfers_no_dinner = parseInt(golferonlybox.value);
	var total_golfers = golfers + golfers_no_dinner;
	if (angelbox.checked || (golfers_included == 0 && total_golfers >= 4))
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

	if (otherbox.value) {
		var otherval = parseInt(otherbox.value);
		if (!isNaN(otherval))
			total += parseInt(otherbox.value);
	}

	// If no sponsorship, hide the "agree to publish my name" checkbox.
	if (total > 0)
		sponsor_agree_div.style.display = "block";
	else
		sponsor_agree_div.style.display = "none";

	golfers_included += go_golfers;

	// Calculate price for additional golfers and dinners.
	if (golfers > golfers_included)
		total += golf_price * (golfers - golfers_included);
	golfers_included = Math.max(0, golfers_included - golfers);
	if (golfers_no_dinner > golfers_included)
		total += golf_only_price * (golfers_no_dinner - golfers_included);
	golfers_included = Math.max(0, golfers_included - golfers_no_dinner);
	dinners_included += golfers_included;
	var dinners = parseInt(dinnerbox.value);
	if (dinners > dinners_included)
		total += dinner_price * (dinners - dinners_included);

	totalbox.value = total;
	totalbox_c.value = add_commas(total);
	credits = parseInt(creditbox.value);
	creditbox_c.value = add_commas(credits);
	netdue = total - credits < 0 ? 0 : total - credits;
	netbox.value = netdue;
	netbox_c.value = add_commas(netdue);
}

function adjust_selector(e, max, sold_out) {
	if (max < 4 && !sold_out)
		max = 4;
	var options = e.getElementsByTagName("option");
	var len = options.length;
	for (var i = len - 1; i > max; i--)
		e.removeChild(options[i]);
	for (var i = options.length; i < max + 1; i++) {
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
	otherbox.onkeyup = recalculate;
	otherbox.onkeypress = ignore_enter;
	var agreebox = document.getElementById("entry_agree");
	agreebox.onclick = recalculate;
	var printednamesbox = document.getElementById("entry_printednames");
	printednamesbox.onkeypress = ignore_enter;
	var selectbox = document.getElementById("entry_num_golfers");
	selectbox.onchange = recalculate;
	selectbox = document.getElementById("entry_num_golfers_no_dinner");
	if (selectbox)
		selectbox.onchange = recalculate;
	selectbox = document.getElementById("entry_num_dinners");
	selectbox.onchange = recalculate;
	var show_go_campaign_box = document.getElementById("checkbox_show_go_campaign");
	show_go_campaign_box.onchange = recalculate;
}
