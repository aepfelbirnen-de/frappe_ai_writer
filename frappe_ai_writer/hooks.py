app_name = "frappe_ai_writer"
app_title = "Frappe AI Writer"
app_publisher = "aepfel+birnen IT GmbH"
app_description = "AI proofreading for Frappe and ERPNext text fields, powered by Claude"
app_email = "it@aepfelbirnen.com"
app_license = "MIT"
app_logo_url = "/assets/frappe_ai_writer/images/frappe_ai_writer-logo.svg"

required_apps = ["frappe"]

# Apps screen (/apps); v16 redirects /app to /desk
add_to_apps_screen = [
    {
        "name": app_name,
        "logo": app_logo_url,
        "title": "AI Writer",
        "route": "/app/ai-writer",
        "has_permission": "frappe_ai_writer.permissions.has_app_screen_access",
    }
]

# Desk assets
app_include_js = "frappe_ai_writer-desk.bundle.js"
app_include_css = "frappe_ai_writer-desk.bundle.css"

# Boot
boot_session = "frappe_ai_writer.boot.boot_session"

# Installation
before_install = "frappe_ai_writer.install.before_install"
after_install = "frappe_ai_writer.install.after_install"
after_migrate = "frappe_ai_writer.install.after_migrate"
