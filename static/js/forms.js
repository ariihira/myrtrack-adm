document.addEventListener("DOMContentLoaded", function() {
    const dropdowns = document.querySelectorAll(".dropdown-checkbox");

    dropdowns.forEach(function(drop) {
        const button = drop.querySelector(".dropbtn");
        const content = drop.querySelector(".dropdown-content");
        button.setAttribute("data-default", button.textContent);

        const checkboxes = Array.from(drop.querySelectorAll('input[type="checkbox"]'));

        // update dropdown text
        function updateDropdownText() {
            const checked = checkboxes.filter(c => c.checked);
            if (checked.length === 0) {
                button.textContent = button.getAttribute("data-default");
            } else {
                const selectedNames = checked.map(c => {
                    const label = c.closest('label');
                    return label ? label.textContent.trim() : '';
                });
                button.textContent = selectedNames.join(", ");
            }
        }

        // attach change listener to checkboxes
        checkboxes.forEach(cb => cb.addEventListener("change", updateDropdownText));

        // search input functionality
        const searchInput = drop.querySelector(".dropdown-search");
        if (searchInput) {
            searchInput.addEventListener("input", function() {
                const query = this.value.toLowerCase();
                checkboxes.forEach(cb => {
                    const label = cb.closest('label');
                    if (!label) return;
                    label.style.display = label.textContent.toLowerCase().includes(query) ? '' : 'none';
                });
            });
        }

        // toggle dropdown
        button.addEventListener("click", function(e) {
            e.stopPropagation();
            content.classList.toggle("show");
        });

        content.addEventListener("click", e => e.stopPropagation());
    });

    // close dropdowns when clicking outside
    window.addEventListener("click", function() {
    document.querySelectorAll(".dropdown-checkbox").forEach(function(drop) {
        const content = drop.querySelector(".dropdown-content");
        content.classList.remove("show");

        // reset search input
        const searchInput = drop.querySelector(".dropdown-search");
        if (searchInput) {
            searchInput.value = ''; // clear the search box
        }

        // show all options again
        drop.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            const label = cb.closest('label');
            if (label) label.style.display = ''; // make sure all labels are visible
        });
    });
});

    // poster preview
    const posterInput = document.getElementById("title_img");
    const posterPreview = document.getElementById("posterPreview");
    if (posterInput && posterPreview) {
        posterInput.addEventListener("change", function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    posterPreview.src = e.target.result;
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // validation: require at least 1 selection
    document.querySelectorAll("form").forEach(form => {
        form.addEventListener("submit", function(e) {
            let isValid = true;

            function validateCheckboxGroup(name, errorId, message) {
                const checkboxes = form.querySelectorAll(`input[name="${name}"]`);
                if (checkboxes.length === 0) return true; // this form doesn't have this group → skip

                const selected = Array.from(checkboxes).filter(cb => cb.checked);
                let errorMsg = form.querySelector(`#${errorId}`);

                if (!errorMsg) {
                    errorMsg = document.createElement("div");
                    errorMsg.id = errorId;
                    errorMsg.style.color = "red";
                    errorMsg.style.fontSize = "0.9em";
                    errorMsg.style.marginTop = "5px";
                    const dropdown = checkboxes[0]?.closest(".dropdown-checkbox");
                    if (dropdown) dropdown.appendChild(errorMsg);
                }

                if (selected.length === 0) {
                    errorMsg.textContent = message;
                    return false;
                } else {
                    errorMsg.textContent = "";
                    return true;
                }
            }

            // run validators scoped to this form only
            const validShows = validateCheckboxGroup("showtitles[]", "showtitles-error", "Please select at least one show.");
            const validCategories = validateCheckboxGroup("categories[]", "categories-error", "Please select at least one category.");

            if (!validShows || !validCategories) {
                e.preventDefault();
                isValid = false;
            }

            return isValid;
        });
    });

});
