#!/usr/bin/env python3
"""
Custom exception classes for ImageSet Generator

Provides domain-specific exceptions with detailed context for better error handling
and debugging. All exceptions inherit from a base exception class for consistent
exception handling patterns.
"""


class ImageSetGeneratorError(Exception):
    """Base exception class for all ImageSet Generator errors"""
    
    def __init__(self, message, details=None, original_error=None):
        """
        Initialize exception with detailed context.
        
        Args:
            message: Human-readable error message
            details: Dict with additional context (catalog, version, etc.)
            original_error: Original exception if this is a wrapper
        """
        self.message = message
        self.details = details or {}
        self.original_error = original_error
        super().__init__(self.format_message())
    
    def format_message(self):
        """Format detailed error message with context"""
        msg = self.message
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            msg = f"{msg} ({details_str})"
        if self.original_error:
            msg = f"{msg} - Caused by: {str(self.original_error)}"
        return msg


class CatalogError(ImageSetGeneratorError):
    """Raised when catalog operations fail"""
    
    def __init__(self, message, catalog=None, version=None, original_error=None):
        """
        Initialize catalog error.
        
        Args:
            message: Error message
            catalog: Catalog identifier or URL
            version: Version string
            original_error: Original exception
        """
        details = {}
        if catalog:
            details['catalog'] = catalog
        if version:
            details['version'] = version
        super().__init__(message, details, original_error)


class CatalogRenderError(CatalogError):
    """Raised when OPM render command fails"""
    pass


class CatalogParseError(CatalogError):
    """Raised when catalog data parsing fails"""
    pass


class OperatorError(ImageSetGeneratorError):
    """Raised when operator operations fail"""
    
    def __init__(self, message, operator=None, channel=None, version=None, original_error=None):
        """
        Initialize operator error.
        
        Args:
            message: Error message
            operator: Operator name
            channel: Channel name
            version: Version string
            original_error: Original exception
        """
        details = {}
        if operator:
            details['operator'] = operator
        if channel:
            details['channel'] = channel
        if version:
            details['version'] = version
        super().__init__(message, details, original_error)


class OperatorNotFoundError(OperatorError):
    """Raised when an operator cannot be found"""
    pass


class InvalidChannelError(OperatorError):
    """Raised when a channel is invalid or not available"""
    pass


class VersionError(ImageSetGeneratorError):
    """Raised when version operations fail"""
    
    def __init__(self, message, version=None, min_version=None, max_version=None, original_error=None):
        """
        Initialize version error.
        
        Args:
            message: Error message
            version: Version string
            min_version: Minimum version
            max_version: Maximum version
            original_error: Original exception
        """
        details = {}
        if version:
            details['version'] = version
        if min_version:
            details['min_version'] = min_version
        if max_version:
            details['max_version'] = max_version
        super().__init__(message, details, original_error)


class InvalidVersionError(VersionError):
    """Raised when a version string is malformed"""
    pass


class VersionComparisonError(VersionError):
    """Raised when version comparison fails"""
    pass


class ConfigurationError(ImageSetGeneratorError):
    """Raised when configuration is invalid"""
    
    def __init__(self, message, config_key=None, config_value=None, original_error=None):
        """
        Initialize configuration error.
        
        Args:
            message: Error message
            config_key: Configuration key that failed
            config_value: Invalid configuration value
            original_error: Original exception
        """
        details = {}
        if config_key:
            details['config_key'] = config_key
        if config_value:
            details['config_value'] = config_value
        super().__init__(message, details, original_error)


class FileOperationError(ImageSetGeneratorError):
    """Raised when file operations fail"""
    
    def __init__(self, message, file_path=None, operation=None, original_error=None):
        """
        Initialize file operation error.
        
        Args:
            message: Error message
            file_path: Path to file that failed
            operation: Operation type (read, write, delete, etc.)
            original_error: Original exception
        """
        details = {}
        if file_path:
            details['file_path'] = file_path
        if operation:
            details['operation'] = operation
        super().__init__(message, details, original_error)


class NetworkError(ImageSetGeneratorError):
    """Raised when network operations fail"""
    
    def __init__(self, message, url=None, status_code=None, original_error=None):
        """
        Initialize network error.
        
        Args:
            message: Error message
            url: URL that failed
            status_code: HTTP status code if applicable
            original_error: Original exception
        """
        details = {}
        if url:
            details['url'] = url
        if status_code:
            details['status_code'] = status_code
        super().__init__(message, details, original_error)


class GenerationError(ImageSetGeneratorError):
    """Raised when ImageSet generation fails"""
    
    def __init__(self, message, stage=None, original_error=None):
        """
        Initialize generation error.
        
        Args:
            message: Error message
            stage: Generation stage that failed (validation, rendering, etc.)
            original_error: Original exception
        """
        details = {}
        if stage:
            details['stage'] = stage
        super().__init__(message, details, original_error)
