$(document).ready(function() {
    let select_elements = document.getElementsByClassName("select2-selection--single");

    for (el of select_elements) {
        el.style.backgroundColor = "#3498DB";
        el.style.color = "white";
        el.style.height = "100%";
    }

    document.querySelectorAll('b[role="presentation"]').forEach(function (el) {
        el.style.color = "white";
        el.style.borderTop = "6px solid white"
    });

});
