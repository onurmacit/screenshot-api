package services

import (
	"errors"
	"fmt"
)

// Domain-specific error types for proper HTTP status mapping
var (
	ErrSelectorNotFound   = errors.New("selector not found")
	ErrSelectorNotVisible = errors.New("selector not visible")
	ErrSelectorTimeout    = errors.New("selector timeout")
	ErrInvalidSelector    = errors.New("invalid selector syntax")
)

// SelectorError wraps selector-related errors with context
type SelectorError struct {
	Selector  string
	Operation string // "find", "wait", "scroll", "capture", "bounds"
	Err       error
}

func (e *SelectorError) Error() string {
	return fmt.Sprintf("selector '%s' %s failed: %v", e.Selector, e.Operation, e.Err)
}

func (e *SelectorError) Unwrap() error {
	return e.Err
}

// IsClientError returns true if error should be 4xx, not 5xx
func IsClientError(err error) bool {
	var selectorErr *SelectorError
	if errors.As(err, &selectorErr) {
		return errors.Is(selectorErr.Err, ErrSelectorNotFound) ||
			errors.Is(selectorErr.Err, ErrSelectorNotVisible) ||
			errors.Is(selectorErr.Err, ErrInvalidSelector)
	}
	return false
}

// IsSelectorError checks if the error is a SelectorError
func IsSelectorError(err error) bool {
	var selectorErr *SelectorError
	return errors.As(err, &selectorErr)
}
