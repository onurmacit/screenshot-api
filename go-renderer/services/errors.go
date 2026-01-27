package services

import (
	"errors"
	"fmt"
	"strings"
)

// Domain-specific error types for proper HTTP status mapping
var (
	ErrSelectorNotFound     = errors.New("selector not found")
	ErrSelectorNotVisible   = errors.New("selector not visible")
	ErrSelectorTimeout      = errors.New("selector timeout")
	ErrInvalidSelector      = errors.New("invalid selector syntax")
	ErrSelectorZeroDimension = errors.New("selector element has zero dimensions")
	ErrSelectorOffScreen    = errors.New("selector element is off-screen")
)

// SelectorError wraps selector-related errors with context
type SelectorError struct {
	Selector  string
	Operation string // "find", "wait", "scroll", "capture", "bounds", "validate", "visibility"
	Err       error
}

func (e *SelectorError) Error() string {
	// Provide user-friendly error messages
	switch e.Operation {
	case "find":
		return fmt.Sprintf("Element not found for selector '%s'. Make sure the selector is correct and the element exists on the page. Error: %v", e.Selector, e.Err)
	case "wait":
		return fmt.Sprintf("Element '%s' did not become stable/visible within timeout. The element might be animated or dynamically loaded. Error: %v", e.Selector, e.Err)
	case "visibility":
		return fmt.Sprintf("Element '%s' exists but is not visible (display:none, visibility:hidden, or zero opacity). Error: %v", e.Selector, e.Err)
	case "bounds":
		return fmt.Sprintf("Could not determine bounding box for '%s'. Element might have zero dimensions or be off-screen. Error: %v", e.Selector, e.Err)
	case "validate":
		return fmt.Sprintf("Invalid selector syntax: '%s'. Use valid CSS selectors (e.g., .class, #id, tag) or XPath (starting with / or //). Error: %v", e.Selector, e.Err)
	case "capture":
		return fmt.Sprintf("Failed to capture screenshot of element '%s'. Error: %v", e.Selector, e.Err)
	default:
		return fmt.Sprintf("Selector '%s' %s failed: %v", e.Selector, e.Operation, e.Err)
	}
}

func (e *SelectorError) Unwrap() error {
	return e.Err
}

// UserFriendlyMessage returns a simplified error message for API responses
func (e *SelectorError) UserFriendlyMessage() string {
	switch e.Operation {
	case "find":
		return fmt.Sprintf("Element not found: '%s'", e.Selector)
	case "wait":
		return fmt.Sprintf("Element unstable or loading: '%s'", e.Selector)
	case "visibility":
		return fmt.Sprintf("Element hidden: '%s'", e.Selector)
	case "bounds":
		return fmt.Sprintf("Element has no visible area: '%s'", e.Selector)
	case "validate":
		return fmt.Sprintf("Invalid selector: '%s'", e.Selector)
	case "capture":
		return fmt.Sprintf("Capture failed for: '%s'", e.Selector)
	default:
		return fmt.Sprintf("Selector error: '%s'", e.Selector)
	}
}

// Hint provides troubleshooting suggestions
func (e *SelectorError) Hint() string {
	switch e.Operation {
	case "find":
		return "Tips: 1) Check if the element exists on the page, 2) Add 'delay' parameter to wait for dynamic content, 3) Use 'wait_for_selector' for SPAs, 4) Try using a more specific selector"
	case "wait":
		return "Tips: 1) Increase 'delay' parameter, 2) Use 'wait_for_selector_state: visible', 3) Element might be inside an iframe (not supported yet)"
	case "visibility":
		return "Tips: 1) The element has display:none or visibility:hidden, 2) Check if the element is behind a modal, 3) Try scrolling first with 'scroll_into_view'"
	case "bounds":
		return "Tips: 1) Element might be collapsed (height/width: 0), 2) Try 'selector_padding' to expand capture area, 3) Element might be positioned off-screen"
	case "validate":
		return "Tips: CSS selectors start with . (class), # (id), or tag name. XPath selectors start with / or //. Avoid special characters like < > { }"
	default:
		return ""
	}
}

// IsClientError returns true if error should be 4xx, not 5xx
func IsClientError(err error) bool {
	var selectorErr *SelectorError
	if errors.As(err, &selectorErr) {
		// Check underlying error
		if errors.Is(selectorErr.Err, ErrSelectorNotFound) ||
			errors.Is(selectorErr.Err, ErrSelectorNotVisible) ||
			errors.Is(selectorErr.Err, ErrInvalidSelector) ||
			errors.Is(selectorErr.Err, ErrSelectorZeroDimension) {
			return true
		}
		// Also check error message patterns
		errMsg := selectorErr.Err.Error()
		if strings.Contains(errMsg, "not found") ||
			strings.Contains(errMsg, "not visible") ||
			strings.Contains(errMsg, "invalid") ||
			strings.Contains(errMsg, "zero dimension") {
			return true
		}
	}
	return false
}

// IsSelectorError checks if the error is a SelectorError
func IsSelectorError(err error) bool {
	var selectorErr *SelectorError
	return errors.As(err, &selectorErr)
}

// GetSelectorError extracts SelectorError from error chain
func GetSelectorError(err error) *SelectorError {
	var selectorErr *SelectorError
	if errors.As(err, &selectorErr) {
		return selectorErr
	}
	return nil
}
