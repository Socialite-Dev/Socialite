function init_callbacks_post_form() {
    let form = document.getElementById("post-form");

    form.addEventListener("submit", (event) => {
        let submitter = event.submitter;
        event.preventDefault();
        
        fetch(form.action, { method: "POST", body: new FormData(form) }).then((resp) => {
            if (resp.ok) {
                resp.json().then((map) => {
                    d = new Map(Object.entries(map));
                    let elem = document.getElementById("feed-parent");
                    if (d.has("elem")) {

                        const e = document.createElement('template');
                        e.innerHTML = d.get("elem").trim();
                        
                        console.log(e);
                        elem.prepend(e.content.firstChild)
                    } else {
                        alert("Failed to post")
                    }
                })
            }
        });
    });
}
document.addEventListener('DOMContentLoaded', init_callbacks_post_form, false);

function try_group_delete(id) {
    if (window.confirm("Are you sure you want to delete this group? THIS CANNOT BE UNDONE")) {
        fetch("/delete_group", { method: "POST", 
            body: JSON.stringify({"id": id}),
            headers: {
                "Content-Type": "application/json"
            }
        }).then((resp) => {
            if (resp.ok) {
                window.location.replace("/")
            } else {
                alert("Failed to delete")
            }
        })
    }
}

function try_delete_post(target_t, post_id) {
    if (window.confirm("Are you sure want to delete this post? THIS CANNOT BE UNDONE")) {
        fetch("/delete_post", { method: "POST",
            body: JSON.stringify({"target_t": target_t, "post_id": post_id}),
            headers: {
                "Content-Type": "application/json"
            }
        }).then((resp) => {
            if (resp.ok) {
                window.location.replace("/")
            } else {
                alert("Failed to delete")
            }
        })
    }
}
