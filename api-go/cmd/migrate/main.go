package main

import (
	"fmt"
	"log"
	"os"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/postgres"
	_ "github.com/golang-migrate/migrate/v4/source/file"
)

func main() {
	databaseURL := os.Getenv("DATABASE_URL")
	if databaseURL == "" {
		log.Fatal("DATABASE_URL environment variable is required")
	}

	// Convert asyncpg URL to standard postgres URL
	// postgresql+asyncpg://... -> postgres://...
	if len(databaseURL) > 20 && databaseURL[:19] == "postgresql+asyncpg:" {
		databaseURL = "postgres:" + databaseURL[19:]
	} else if len(databaseURL) > 11 && databaseURL[:11] == "postgresql:" {
		databaseURL = "postgres:" + databaseURL[11:]
	}

	migrationsPath := "file://migrations"
	if os.Getenv("MIGRATIONS_PATH") != "" {
		migrationsPath = os.Getenv("MIGRATIONS_PATH")
	}

	m, err := migrate.New(migrationsPath, databaseURL)
	if err != nil {
		log.Fatalf("Failed to create migrate instance: %v", err)
	}
	defer m.Close()

	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	switch os.Args[1] {
	case "up":
		if err := m.Up(); err != nil && err != migrate.ErrNoChange {
			log.Fatalf("Migration up failed: %v", err)
		}
		fmt.Println("✅ Migrations applied successfully")

	case "down":
		if err := m.Steps(-1); err != nil && err != migrate.ErrNoChange {
			log.Fatalf("Migration down failed: %v", err)
		}
		fmt.Println("✅ Rolled back one migration")

	case "version":
		version, dirty, err := m.Version()
		if err != nil {
			if err == migrate.ErrNilVersion {
				fmt.Println("No migrations have been applied yet")
				return
			}
			log.Fatalf("Failed to get version: %v", err)
		}
		fmt.Printf("Current version: %d\nDirty: %v\n", version, dirty)

	case "force":
		if len(os.Args) < 3 {
			log.Fatal("Usage: migrate force <version>")
		}
		var version int
		fmt.Sscanf(os.Args[2], "%d", &version)
		if err := m.Force(version); err != nil {
			log.Fatalf("Force version failed: %v", err)
		}
		fmt.Printf("✅ Forced version to %d\n", version)

	case "drop":
		if err := m.Drop(); err != nil {
			log.Fatalf("Drop failed: %v", err)
		}
		fmt.Println("✅ All tables dropped")

	default:
		fmt.Printf("Unknown command: %s\n", os.Args[1])
		printUsage()
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Println("Database Migration Tool")
	fmt.Println("")
	fmt.Println("Usage: migrate <command> [args]")
	fmt.Println("")
	fmt.Println("Commands:")
	fmt.Println("  up            Apply all pending migrations")
	fmt.Println("  down          Rollback the last migration")
	fmt.Println("  version       Show current migration version")
	fmt.Println("  force <N>     Force set version (use with caution)")
	fmt.Println("  drop          Drop all tables (DANGEROUS)")
	fmt.Println("")
	fmt.Println("Environment Variables:")
	fmt.Println("  DATABASE_URL      PostgreSQL connection string (required)")
	fmt.Println("  MIGRATIONS_PATH   Path to migrations (default: file://migrations)")
}
