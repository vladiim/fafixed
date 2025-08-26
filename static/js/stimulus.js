console.log("Loading stimulus.js...")

// Load Stimulus and Turbo from node_modules
import { Application } from "@hotwired/stimulus"
import "@hotwired/turbo"

console.log("Stimulus and Turbo loaded from node_modules")

// Import controllers
import AccountDropdownController from "./controllers/account_dropdown_controller.js"
import MessageAlertController from "./controllers/message_alert_controller.js"
import DropdownController from "./controllers/dropdown_controller.js"

const application = Application.start()

// Register controllers
application.register("account-dropdown", AccountDropdownController)
application.register("message-alert", MessageAlertController)
application.register("dropdown", DropdownController)

// Configure Stimulus development experience
application.debug = true
window.Stimulus = application

console.log("Stimulus loaded, registered controllers:", application.router.modulesByIdentifier)

// Turbo configuration to prevent message accumulation
document.addEventListener('turbo:before-cache', () => {
  // Remove all message alerts before caching the page
  document.querySelectorAll('[data-controller="message-alert"]').forEach(el => el.remove())
})

export { application }