var menu_visible = false;

function init_menu() {
	var menu_container = document.getElementById("ccmenu");
	var nav_div = document.getElementById("nav");
	menu_visible = false;
	menu_container.className = "off";
	nav_div.style.left = "";
	menu_container.onclick = function() {
		if (menu_visible) {
			menu_visible = false;
			menu_container.className = "off";
			nav_div.style.left = "";
		} else {
			menu_visible = true;
			menu_container.className = "on";
			nav_div.style.left = "0";
		}
	};
	document.addEventListener('click', function(e) {
		if (menu_visible && !menu_container.contains(e.target) && !nav_div.contains(e.target)) {
			menu_container.className = "off";
			nav_div.style.left = "";
			menu_visible = false;
		}
	});
}	
