// Load Stimulus and Turbo from CDN
import { Application, Controller } from "https://unpkg.com/@hotwired/stimulus/dist/stimulus.js"
import "https://unpkg.com/@hotwired/turbo/dist/turbo.es2017-esm.js"

// Account Dropdown Controller
class AccountDropdownController extends Controller {
  static targets = ["dropdown", "dropdownButton", "buttonText", "chevron", "submitButton", "selectedAccounts", "selectedList", "hiddenInputs"]

  connect() {
    this.selectedAccounts = new Set()
    this.updateUI()
    
    // Close dropdown when clicking outside
    document.addEventListener('click', this.handleOutsideClick.bind(this))
  }

  disconnect() {
    document.removeEventListener('click', this.handleOutsideClick.bind(this))
  }

  handleOutsideClick(event) {
    if (!this.element.contains(event.target)) {
      this.closeDropdown()
    }
  }

  toggleDropdown() {
    if (this.dropdownTarget.classList.contains('hidden')) {
      this.openDropdown()
    } else {
      this.closeDropdown()
    }
  }

  openDropdown() {
    this.dropdownTarget.classList.remove('hidden')
    this.chevronTarget.classList.add('rotate-180')
  }

  closeDropdown() {
    this.dropdownTarget.classList.add('hidden')
    this.chevronTarget.classList.remove('rotate-180')
  }

  toggleAccount(event) {
    event.preventDefault()
    
    const accountElement = event.currentTarget
    const accountId = accountElement.dataset.accountId
    const accountName = accountElement.dataset.accountName
    const accountOrg = accountElement.dataset.accountOrg
    const checkbox = accountElement.querySelector('.account-checkbox')
    const checkIcon = checkbox.querySelector('i')
    
    if (this.selectedAccounts.has(accountId)) {
      // Deselect
      this.selectedAccounts.delete(accountId)
      checkbox.classList.remove('bg-brand-black', 'border-brand-black')
      checkbox.classList.add('border-gray-300')
      checkIcon.classList.add('hidden')
    } else {
      // Select
      this.selectedAccounts.add(accountId)
      checkbox.classList.add('bg-brand-black', 'border-brand-black')
      checkbox.classList.remove('border-gray-300')
      checkIcon.classList.remove('hidden')
    }
    
    this.updateUI()
  }

  updateUI() {
    this.updateButtonText()
    this.updateSelectedDisplay()
    this.updateHiddenInputs()
    this.updateSubmitButton()
  }

  updateButtonText() {
    const count = this.selectedAccounts.size
    if (count === 0) {
      this.buttonTextTarget.textContent = "Select accounts to import..."
      this.buttonTextTarget.classList.add('text-gray-500')
      this.buttonTextTarget.classList.remove('text-brand-black')
    } else if (count === 1) {
      this.buttonTextTarget.textContent = "1 account selected"
      this.buttonTextTarget.classList.remove('text-gray-500')
      this.buttonTextTarget.classList.add('text-brand-black')
    } else {
      this.buttonTextTarget.textContent = `${count} accounts selected`
      this.buttonTextTarget.classList.remove('text-gray-500')
      this.buttonTextTarget.classList.add('text-brand-black')
    }
  }

  updateSelectedDisplay() {
    if (this.selectedAccounts.size === 0) {
      this.selectedAccountsTarget.classList.add('hidden')
    } else {
      this.selectedAccountsTarget.classList.remove('hidden')
      
      this.selectedListTarget.innerHTML = ''
      this.selectedAccounts.forEach(accountId => {
        // Find the account element to get name and org
        const accountElement = this.element.querySelector(`[data-account-id="${accountId}"]`)
        const name = accountElement.dataset.accountName
        const org = accountElement.dataset.accountOrg
        
        const selectedItem = document.createElement('div')
        selectedItem.className = 'flex items-center justify-between p-3 bg-gray-50 rounded-lg'
        selectedItem.innerHTML = `
          <div>
            <h5 class="font-medium text-brand-black text-sm">${name}</h5>
            <p class="text-xs text-gray-600">${org}</p>
          </div>
          <button type="button" data-account-id="${accountId}" data-action="click->account-dropdown#removeAccount" class="text-gray-400 hover:text-brand-red">
            <i class="fas fa-times"></i>
          </button>
        `
        this.selectedListTarget.appendChild(selectedItem)
      })
    }
  }

  updateHiddenInputs() {
    this.hiddenInputsTarget.innerHTML = ''
    this.selectedAccounts.forEach(accountId => {
      const input = document.createElement('input')
      input.type = 'hidden'
      input.name = 'selected_accounts'
      input.value = accountId
      this.hiddenInputsTarget.appendChild(input)
    })
  }

  updateSubmitButton() {
    const hasSelected = this.selectedAccounts.size > 0
    this.submitButtonTarget.disabled = !hasSelected
    
    if (hasSelected) {
      this.submitButtonTarget.classList.remove('opacity-50', 'cursor-not-allowed')
      this.submitButtonTarget.classList.add('hover:bg-gray-800')
    } else {
      this.submitButtonTarget.classList.add('opacity-50', 'cursor-not-allowed')
      this.submitButtonTarget.classList.remove('hover:bg-gray-800')
    }
  }

  removeAccount(event) {
    event.preventDefault()
    const accountId = event.currentTarget.dataset.accountId
    
    this.selectedAccounts.delete(accountId)
    
    // Update the visual state of the checkbox in dropdown
    const accountElement = this.element.querySelector(`[data-account-id="${accountId}"]`)
    if (accountElement) {
      const checkbox = accountElement.querySelector('.account-checkbox')
      const checkIcon = checkbox.querySelector('i')
      checkbox.classList.remove('bg-brand-black', 'border-brand-black')
      checkbox.classList.add('border-gray-300')
      checkIcon.classList.add('hidden')
    }
    
    this.updateUI()
  }
}

const application = Application.start()

// Register controllers
application.register("account-dropdown", AccountDropdownController)

// Configure Stimulus development experience
application.debug = false
window.Stimulus = application

export { application }