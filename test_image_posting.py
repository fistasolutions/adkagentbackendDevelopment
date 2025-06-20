#!/usr/bin/env python3
"""
Test script for image posting functionality
"""

import json
import sys
import os

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from routes.post_on_twitter import validate_image_url, process_tweets

def test_image_url_validation():
    """Test image URL validation"""
    print("Testing image URL validation...")
    
    # Test with valid image URLs
    valid_urls = [
        "https://res.cloudinary.com/dgrk02mjc/image/upload/v1749912216/pasted-2025.05.15-11.21.46_hajnch.png",
        "https://res.cloudinary.com/dgrk02mjc/image/upload/v1749912220/pasted-2025.05.15-11.21.46_tzohpb.png"
    ]
    
    for url in valid_urls:
        is_valid = validate_image_url(url)
        print(f"URL: {url}")
        print(f"Valid: {is_valid}")
        print("-" * 50)
    
    # Test with invalid URL
    invalid_url = "https://example.com/nonexistent.jpg"
    is_valid = validate_image_url(invalid_url)
    print(f"Invalid URL: {invalid_url}")
    print(f"Valid: {is_valid}")
    print("-" * 50)

def test_image_url_parsing():
    """Test image URL parsing from JSON"""
    print("\nTesting image URL parsing...")
    
    # Test JSON string
    json_string = '["https://res.cloudinary.com/dgrk02mjc/image/upload/v1749912216/pasted-2025.05.15-11.21.46_hajnch.png", "https://res.cloudinary.com/dgrk02mjc/image/upload/v1749912220/pasted-2025.05.15-11.21.46_tzohpb.png"]'
    
    try:
        parsed_urls = json.loads(json_string)
        print(f"Parsed URLs: {parsed_urls}")
        print(f"Number of URLs: {len(parsed_urls)}")
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
    
    print("-" * 50)

def test_row_processing():
    """Test row processing with different formats"""
    print("\nTesting row processing...")
    
    # Test regular posts format (5 columns)
    regular_row = (1, "Test tweet content", 123, 456, '["https://res.cloudinary.com/dgrk02mjc/image/upload/v1749912216/pasted-2025.05.15-11.21.46_hajnch.png"]')
    print(f"Regular row: {regular_row}")
    print(f"Row length: {len(regular_row)}")
    
    # Test scheduled posts format (6 columns)
    scheduled_row = (2, "Scheduled tweet content", 123, 456, "2024-01-01 12:00:00", '["https://res.cloudinary.com/dgrk02mjc/image/upload/v1749912220/pasted-2025.05.15-11.21.46_tzohpb.png"]')
    print(f"Scheduled row: {scheduled_row}")
    print(f"Row length: {len(scheduled_row)}")
    
    print("-" * 50)

if __name__ == "__main__":
    print("Testing Image Posting Functionality")
    print("=" * 50)
    
    test_image_url_validation()
    test_image_url_parsing()
    test_row_processing()
    
    print("\nTest completed!") 