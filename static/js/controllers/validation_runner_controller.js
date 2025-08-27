import { Controller } from "@hotwired/stimulus"

// Simple validation runner controller - just handles UI interactions
// Real-time updates are handled by turbo-cable-stream-source + django-lifecycle
export default class extends Controller {
  connect() {
    // Auto-close dropdown when form is submitted via Turbo
    this.element.addEventListener("turbo:submit-start", () => {
      this.closeDropdown()
    })
  }
  
  closeDropdown() {
    // Find the parent dropdown and close it
    const dropdownController = this.element.closest('[data-controller*="dropdown"]')
    if (dropdownController) {
      const menu = dropdownController.querySelector('[data-dropdown-target="menu"]')
      if (menu) {
        menu.classList.add('hidden')
      }
    }
  }
}