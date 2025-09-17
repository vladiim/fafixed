import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["categorySelect"]

  connect() {
    // Find the connection select by its ID from the form
    this.connectionSelect = document.getElementById('id_connection')
    if (this.connectionSelect) {
      this.connectionSelect.addEventListener('change', () => this.connectionChanged())
    }
  }

  connectionChanged() {
    if (!this.connectionSelect) return

    const connectionId = this.connectionSelect.value

    if (!connectionId) {
      // Reset category dropdown
      const categorySelect = this.categorySelectTarget.querySelector('select')
      if (categorySelect) {
        categorySelect.innerHTML = '<option value="">Select Xero Organization first...</option>'
        categorySelect.disabled = true
      }
      return
    }

    // Use Turbo to fetch and replace the category dropdown
    window.Turbo.visit(`/quality/connections/${connectionId}/tracking-categories/`, {
      frame: 'category-dropdown-frame'
    })
  }
}