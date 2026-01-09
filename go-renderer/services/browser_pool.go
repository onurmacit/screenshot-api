package services

import (
	"log"
	"os"
	"sync"

	"github.com/go-rod/rod"
	"github.com/go-rod/rod/lib/launcher"
)

// BrowserPool manages a pool of browser instances for efficient rendering
type BrowserPool struct {
	browsers []*rod.Browser
	mutex    sync.Mutex
	current  int
	size     int
}

// NewBrowserPool creates a new browser pool with the specified size
func NewBrowserPool(size int) *BrowserPool {
	pool := &BrowserPool{
		browsers: make([]*rod.Browser, size),
		size:     size,
	}

	// Initialize browsers
	for i := 0; i < size; i++ {
		browser := pool.createBrowser()
		pool.browsers[i] = browser
		log.Printf("Browser %d initialized", i+1)
	}

	log.Printf("Browser pool initialized with %d instances", size)
	return pool
}

// createBrowser creates a new browser instance with optimized settings
func (p *BrowserPool) createBrowser() *rod.Browser {
	// For chromedp/headless-shell image, Chrome is at /headless-shell/headless-shell
	// For other images, Chrome might be at different paths
	chromePath := os.Getenv("CHROME_PATH")
	if chromePath == "" {
		chromePath = "/headless-shell/headless-shell"
	}

	// Launch options for headless Chrome using the bundled binary
	u := launcher.New().
		Bin(chromePath).
		Headless(true).
		Set("disable-gpu").
		Set("disable-dev-shm-usage").
		Set("no-sandbox").
		Set("disable-setuid-sandbox").
		Set("disable-accelerated-2d-canvas").
		Set("no-first-run").
		Set("no-zygote").
		Set("single-process").
		Set("disable-extensions").
		Set("disable-background-networking").
		Set("disable-default-apps").
		Set("disable-sync").
		Set("disable-translate").
		Set("mute-audio").
		Set("hide-scrollbars").
		MustLaunch()

	browser := rod.New().ControlURL(u).MustConnect()
	return browser
}

// Acquire gets a browser from the pool (round-robin)
func (p *BrowserPool) Acquire() *rod.Browser {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	browser := p.browsers[p.current]
	p.current = (p.current + 1) % p.size
	return browser
}

// Close closes all browsers in the pool
func (p *BrowserPool) Close() {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	for i, browser := range p.browsers {
		if browser != nil {
			browser.MustClose()
			log.Printf("Browser %d closed", i+1)
		}
	}
	log.Println("Browser pool closed")
}
