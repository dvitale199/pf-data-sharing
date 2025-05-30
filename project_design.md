This project plan outlines the development of a Streamlit application for sharing data from GCP buckets with specific recipients. The application will support both single sample sharing (with zipping) and multi-sample sharing functionality while tracking all shared data.
Project Overview
The application will be built using Streamlit for the UI and Google Cloud Storage libraries for bucket operations. It will follow a modular design pattern with clear separation of concerns between UI, business logic, and data operations.

### Primary Features

- Single sample sharing with automatic zipping
- Multi-sample sharing to new or existing buckets
- Tracking interface for monitoring shared samples
- Automated email notifications with download links
- Lifecycle management for automatic deletion after 30 days

### Architecture and Project Structure

```
src/
└── core/
    ├── app.py                 # Main application entry point
    ├── requirements.txt       # Project dependencies
    ├── components/
    │   ├── single_sample.py   # Single sample sharing component
    │   ├── multi_sample.py    # Multi-sample sharing component
    │   └── tracking.py        # Tracking and management component
    ├── services/
    │   ├── gcs_service.py     # Google Cloud Storage operations
    │   ├── email_service.py   # Email sending functionality
    │   └── tracking_service.py  # Tracking state management
    └── utils/
        ├── auth.py            # Authentication utilities
        └── file_operations.py # File handling utilities

```

## Core Services

1. GCS Service
Handles all Google Cloud Storage operations including bucket management, object copying, access control, and lifecycle policies. Implements methods for bucket creation/existence checks, object transfers between buckets, permission management, and signed URL generation. Manages automatic deletion policies for temporary data storage.
2. File Operations Utility
Provides specialized file handling capabilities for GCS interactions. Features in-memory zip creation from distributed cloud storage objects and bulk upload functionality. Optimizes large file transfers through stream-based processing without local storage requirements.
3. Email Service
Integrates SendGrid API for automated notification system. Generates preformatted messages with secure download links for single samples and bucket access instructions for bulk shares. Supports HTML content templates and environment variable configuration for credentials.
4. Tracking Service
Maintains JSON-based registry of all shared samples with expiration tracking. Calculates remaining access days and enables historical record filtering. Provides pandas DataFrame interface for UI integration and supports manual entry deletion with associated GCS cleanup.
Streamlit UI Components
5. Single Sample Sharing Interface
•	Accepts sample ID/email inputs through form submission
•	Orchestrates zip creation/transfer workflow
•	Implements progress indicators for long operations
•	Integrates with tracking service for audit logging
6. Multi-Sample Batch Processor
•	Supports CSV/TXT file uploads for bulk operations
•	Provides bucket creation/selection options
•	Displays real-time transfer progress metrics
•	Handles concurrent object copying with error isolation
7. Tracking & Management Dashboard
•	Interactive data grid with dynamic filtering
•	Multi-select deletion interface with confirmation
•	Visual lifecycle expiration indicators
•	Combined GCS/tracking record cleanup system
Infrastructure Components
8. Main Application Orchestrator
•	Initializes service dependencies with resource caching
•	Implements navigation routing between modules
•	Centralizes environment configuration
•	Enables wide-layout presentation for data tables

## Design Pattern Implementation

- **Service Layer Pattern**: Isolates cloud operations, email delivery, and state tracking into independent services with well-defined interfaces. Enables mock testing and technology swaps.
- **Component Architecture**: Decouples UI modules using dedicated rendering functions with injected dependencies. Supports independent development of sharing interfaces and dashboard.
- **Repository Implementation**: File-based tracking system acts as persistent data store with CRUD operations. Abstracted behind service interface for potential database migration.
- **Dependency Management**: Implements singleton-like initialization for cloud clients and service objects. Reduces connection overhead and ensures state consistency.