import asyncio
import httpx
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

from app.core.config import settings
from app.services.cache_service import cache_service


class ValidationService:
    """URL validation and content checking service"""

    def __init__(self):
        self.timeout = 10 # HTTP request timeout
        self.max_redirects = 5
        self.max_content_size = 10 * 1024 * 1024 # 10MB
        self.user_agent = f"{settings.app_name}/{settings.app_version}"

        # Example of blacklist domain
        self.blacklisted_domains = {
            "malware.com",
            "spam.example.com",
            "phishing.test"
        }

        # Suspicious patterns
        self.suspicious_patterns = [
            r"\.tk$",  # Free domains
            r"\.ml$",
            r"\.ga$",
            r"\.cf$",
            r"bit\.ly/[a-zA-Z0-9]{1,3}$",  # Too short bit.ly links
            r"tinyurl\.com/[a-zA-Z0-9]{1,3}$",  # Too short tinyurl links
        ]
        
        # Safe file extensions for content
        self.safe_extensions = {
            ".html", ".htm", ".php", ".asp", ".aspx", ".jsp",
            ".pdf", ".doc", ".docx", ".txt", ".rtf",
            ".jpg", ".jpeg", ".png", ".gif", ".svg",
            ".mp4", ".mp3", ".avi", ".mov"
        }

    async def validate_url(
        self,
        url: str,
        check_accessibility: bool = True,
        check_content: bool = False,
        check_safety: bool = True
    ) -> Dict[str, any]:
        """Comprehensive URL validation"""

        validation_result = {
            "is_valid": False,
            "is_accessible": False,
            "is_safe": True,
            "status_code": None,
            "title": None,
            "content_type": None,
            "content_length": None,
            "redirect_url": None,
            "warnings": [],
            "errors": [],
            "metadata": {}
        }

        try:
            # 1. Basic URL format validation
            if not self._is_valid_url_format(url):
                validation_result["errors"].append("Invalid URL format")
                return validation_result
            
            validation_result["is_valid"] = True

            # 2. Domain safety check
            if check_safety:
                safety_check = await self._check_url_safety(url)
                validation_result["is_safe"] = safety_check["is_safe"]
                if safety_check["warnings"]:
                    validation_result["warnings"].extend(safety_check["warnings"])
                if safety_check["errors"]:
                    validation_result["errors"].extend(safety_check["errors"])

            # 3. Accessibility check
            if check_accessibility:
                access_result = await self._check_url_accessibility(url)
                validation_result.update(access_result)

            # 4. Content analysis
            if check_content and validation_result["is_accessible"]:
                content_result = await self._analyze_content(url)
                validation_result["metadata"].update(content_result)
            
        except Exception as e:
            validation_result["errors"].append(f"Validation error: {str(e)}")

    def _is_valid_url_format(self, url: str) -> bool:
        """Basic URL validation"""
        try:
            result = urlparse(url)
            return all(result.scheme, result.netloc)
        except Exception:
            return False
        
    async def _check_url_safety(self, url: str) -> Dict[str, any]:
        """URL safety check."""

        safety_result = {
            "is_safe": True,
            "warnings": [],
            "errors": []
        }

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            if domain in self.blacklisted_domains:
                safety_result["is_safe"] = False
                safety_result["errors"].append(f"Domain '{domain}' is blacklisted")
                return safety_result
            
            # Check suspicious patterns
            full_url = url.lower() 
            for pattern in self.suspicious_patterns:
                if re.search(pattern, full_url):
                    safety_result["warnings"].append(f"Suspicious URL pattern detected: {pattern}")
            
            # Check for IP address instead of domains
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', domain):
                safety_result["warnings"].append("URL uses IP address instead of domain")

            # Check for suspicious TLDs
            suspicious_tlds = ['.tk', '.ml', '.ga', '.cf', '.click', '.download']
            for tld in suspicious_tlds:
                if domain.endswith(tld):
                    safety_result["warnings"].append(f"Suspicious TLD: {tld}")
            
            # Check URL length (very long URLs can be suspicious)
            if len(url) > 2000:
                safety_result["warnings"].append("Unusually long URL")

        
        except Exception:
            safety_result["errors"].append(f"Safety check error: {str(e)}")
        
        return safety_result
    
    async def _check_url_accessibility(self, url: str) -> Dict[str, any]:
        """URL accessibilty check."""

        access_result = {
            "is_accessible": False,
            "status_code": None,
            "redirect_url": None,
            "response_time": None,
            "content_type": None,
            "content_length": None
        }

        try:
            start_time = datetime.utcnow()

            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                max_redirects=self.max_redirects,
                headers={"User-Agent": self.user_agent}
            ) as client:
                
                response = await client.head(url)

                end_time = datetime.utcnow()
                response_time = (end_time - start_time).total_seconds()

                access_result.update(
                    {
                        "is_accessible": response.status_code < 400,
                        "status_code": response.status_code,
                        "response_time": round(response_time, 3),
                        "content_type": response.headers.get("content-type"),
                        "content_length": response.headers.get("content-length")
                    }
                )

                # Check for redirects
                if str(response.url) != url:
                    access_result["redirect_url"] = str(response.url)

        except httpx.TimeoutException:
            access_result["errors"] = ["Request timeout"]
        except httpx.ConnectError:
            access_result["errors"] = ["Connection failed"]
        except Exception as e:
            access_result["errors"] = [f"Accessibility check failed: {str(e)}"]
        
        return access_result
    
    async def _analyze_content(self, url: str) -> Dict[str, any]:
        """Content analysis"""

        content_result = {
            "has_malicious_content": False,
            "content_warnings": [],
            "language_detected": None,
            "word_count": 0,
            "has_forms": False,
            "external_links": 0,
            "images": 0
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent}
            ) as client:
                
                response = await client.get(url)

                if response.status_code != 200:
                    return content_result
                
                content_type = response.headers.get("content-type", "").lower()

                # Only analyze HTML content
                if "text/html" not in content_type:
                    return content_result
                
                # Only analyze HTML content
                if "text/html" not in content_type:
                    return content_result
                
                # Check content size
                content_length = len(response.content)
                if content_length > self.max_content_size:
                    content_result["content_warnings"].append("Content size exceeds limit")
                    return content_result
                
                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')

                # Basic content analysis
                content_result.update(self._analyze_html_content(soup, url))
        except Exception:
            pass

    def _analyze_html_content(self, soup: BeautifulSoup, base_url: str) -> Dict[str, any]:
        """HTML content analysis."""
        
        analysis = {}
        
        try:
            # Text content analysis
            text_content = soup.get_text()
            words = text_content.split()
            analysis["word_count"] = len(words)
            
            # Language detection (basic)
            if text_content:
                # example
                common_english_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
                common_turkish_words = ['ve', 'bir', 'bu', 'da', 'de', 'ile', 'için', 'olan', 'var', 'den', 'dan']
                
                text_lower = text_content.lower()
                english_count = sum(1 for word in common_english_words if word in text_lower)
                turkish_count = sum(1 for word in common_turkish_words if word in text_lower)
                
                if english_count > turkish_count:
                    analysis["language_detected"] = "en"
                elif turkish_count > 0:
                    analysis["language_detected"] = "tr"
            
            # Form detection
            forms = soup.find_all('form')
            analysis["has_forms"] = len(forms) > 0
            analysis["form_count"] = len(forms)
            
            # External links
            links = soup.find_all('a', href=True)
            external_links = 0
            for link in links:
                href = link['href']
                if href.startswith('http') and not href.startswith(base_url):
                    external_links += 1
            analysis["external_links"] = external_links
            
            # Images
            images = soup.find_all('img')
            analysis["images"] = len(images)
            
            # Script tags (potential security concern)
            scripts = soup.find_all('script')
            analysis["script_count"] = len(scripts)
            
            # Suspicious content patterns
            suspicious_keywords = [
                'virus', 'malware', 'phishing', 'scam', 'hack', 'crack',
                'free money', 'click here now', 'urgent action required',
                'verify account', 'suspended account', 'confirm identity'
            ]
            
            text_lower = text_content.lower()
            found_suspicious = [keyword for keyword in suspicious_keywords if keyword in text_lower]
            
            if found_suspicious:
                analysis["has_malicious_content"] = True
                analysis["content_warnings"].append(f"Suspicious keywords found: {', '.join(found_suspicious)}")
            
            # Iframe detection (potential security risk)
            iframes = soup.find_all('iframe')
            if iframes:
                analysis["content_warnings"].append(f"Contains {len(iframes)} iframe(s)")
            
        except Exception:
            pass
        
        return analysis