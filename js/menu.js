var menu_visible = false;

function init_menu() {
	var menu_container = document.getElementById("ccmenu");
	var nav_div = document.getElementById("nav");
	var orig_left = nav_div.style.left;
	menu_container.onclick = function() {
		menu_container.className = "";
		nav_div.style.left = "0";
		menu_visible = true;
	};
	document.addEventListener('click', function(e) {
		if (menu_visible && !menu_container.contains(e.target) && !nav_div.contains(e.target)) {
			menu_container.className = "visible";
			nav_div.style.left = orig_left;
			menu_visible = false;
		}
	});
}	
