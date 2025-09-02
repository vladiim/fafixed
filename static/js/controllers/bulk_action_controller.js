import { Controller } from "@hotwired/stimulus"

// Extensible controller for bulk actions with checkboxes
// Can be used for issues, transactions, or any other bulk operations
export default class extends Controller {
    static targets = ["selectAll", "item", "actionButton", "form"]
    static values = { 
        actionText: String,
        actionTextPlural: String,
        confirmMessage: String,
        requireConfirmation: { type: Boolean, default: false }
    }
    
    connect() {
        this.updateActionButton()
        this.updateSelectAllState()
    }
    
    // Handle select all checkbox toggle
    selectAllChanged() {
        const isChecked = this.selectAllTarget.checked
        
        this.itemTargets.forEach(checkbox => {
            checkbox.checked = isChecked
        })
        
        this.updateActionButton()
    }
    
    // Handle individual item checkbox toggle
    itemChanged() {
        this.updateSelectAllState()
        this.updateActionButton()
    }
    
    // Update the select all checkbox state (checked, unchecked, or indeterminate)
    updateSelectAllState() {
        if (!this.hasSelectAllTarget || this.itemTargets.length === 0) return
        
        const checkedCount = this.getCheckedItems().length
        const totalCount = this.itemTargets.length
        
        if (checkedCount === 0) {
            this.selectAllTarget.checked = false
            this.selectAllTarget.indeterminate = false
        } else if (checkedCount === totalCount) {
            this.selectAllTarget.checked = true
            this.selectAllTarget.indeterminate = false
        } else {
            this.selectAllTarget.checked = false
            this.selectAllTarget.indeterminate = true
        }
    }
    
    // Update action button state and text
    updateActionButton() {
        if (!this.hasActionButtonTarget) return
        
        const checkedItems = this.getCheckedItems()
        const count = checkedItems.length
        
        // Enable/disable button
        this.actionButtonTarget.disabled = count === 0
        
        // Update button text
        if (count === 0) {
            this.actionButtonTarget.textContent = this.actionTextValue || "Select Items"
        } else if (count === 1) {
            this.actionButtonTarget.textContent = this.actionTextValue || "Process Item"
        } else {
            const pluralText = this.actionTextPluralValue || `Process ${count} Items`
            this.actionButtonTarget.textContent = pluralText.replace('%count%', count)
        }
    }
    
    // Handle form submission with optional confirmation
    submitAction(event) {
        const checkedItems = this.getCheckedItems()
        
        if (checkedItems.length === 0) {
            event.preventDefault()
            return
        }
        
        // Show confirmation if required
        if (this.requireConfirmationValue) {
            const confirmMessage = this.confirmMessageValue || 
                `Are you sure you want to process ${checkedItems.length} item(s)?`
            
            if (!confirm(confirmMessage)) {
                event.preventDefault()
                return
            }
        }
        
        // Allow form submission to proceed
    }
    
    // Get all checked item checkboxes
    getCheckedItems() {
        return this.itemTargets.filter(checkbox => checkbox.checked)
    }
    
    // Get values of all checked items
    getCheckedValues() {
        return this.getCheckedItems().map(checkbox => checkbox.value)
    }
    
    // Programmatically select items by value
    selectItems(values) {
        this.itemTargets.forEach(checkbox => {
            checkbox.checked = values.includes(checkbox.value)
        })
        this.updateSelectAllState()
        this.updateActionButton()
    }
    
    // Programmatically clear all selections
    clearSelection() {
        this.itemTargets.forEach(checkbox => {
            checkbox.checked = false
        })
        this.updateSelectAllState()
        this.updateActionButton()
    }
    
    // Get count of selected items (useful for other controllers)
    get selectedCount() {
        return this.getCheckedItems().length
    }
}