""" utility schema for gRPC and Rest API"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from .url import (
    ShortenUrlRequest as RestShortenUrlRequest,
    ShortenUrlResponse as RestShortenUrlResponse,
    ResolveUrlResponse as RestResolveUrlResponse,
    UrlStatsResponse as RestUrlStatsResponse,
    ListUrlsResponse as RestListUrlsResponse,
    UrlClickResponse,
    ShortenedUrlResponse
)

class GrpcConverter:

    @staticmethod
    def shorten_request_to_rest(grpc_request) -> RestShortenUrlRequest:
        """Convert gRPC ShortenUrlReuest to Rest request"""

        data = {
            "original_url": grpc_request.original_url
        }

        if grpc_request.HasField("custom_code"):
            data["custom_code"] = grpc_request.custom_code

        if grpc_request.HasField("expires_in_days"):
            data["expires_in_days"] = grpc_request.expires_in_days

        return RestShortenUrlRequest(**data)
    

    @staticmethod
    def rest_to_shorten_response(rest_response: RestShortenUrlResponse, grpc_response_class):
        """Convert Rest response to gRPC response"""

        response = grpc_response_class()
        response.short_code = rest_response.short_code
        response.short_url = rest_response.short_url
        response.original_url = rest_response.original_url
        response.created_url = int(response.created_at.timestamp())

        if rest_response.expires_at:
            response.expires_at = int(rest_response.expires_at.timestamp())

    @staticmethod
    def rest_to_resolve_response(rest_response: RestResolveUrlResponse, grpc_response_class):
        """Convert REST resolve response to gRPC response"""

        response = grpc_response_class()
        response.found = rest_response.found
        response.expired = rest_response.expired

        if rest_response.original_url:
            response.original_url = rest_response.original_url

        return response
    
    @staticmethod
    def url_model_to_grpc_url_info(url_model, grpc_url_info_class):
        """Convert SQLAlchemy model to gRPC URLInfo"""

        url_info = grpc_url_info_class()
        url_info.short_code = url_model.short_code
        url_info.original_url = url_model.original_url
        url_info.click_count = url_model.click_count
        url_info.created_at = int(url_model.created_at.timestamp())

        if url_model.expires_at:
            url_info.expires_at = int(url_model.expires_at.timestamp())
            
        return url_info
    
    @staticmethod
    def click_model_to_grpc_click_info(click_model, grpc_click_info_class):
        """Convert SQLAlchemy click model to gRPC ClickInfo"""
        click_info = grpc_click_info_class()
        click_info.timestamp = int(click_model.created_at.timestamp())
        
        if click_model.ip_address:
            click_info.ip_address = click_model.ip_address
        if click_model.user_agent:
            click_info.user_agent = click_model.user_agent
        if click_model.referer:
            click_info.referer = click_model.referer
            
        return click_info
    
    @staticmethod
    def rest_to_stats_response(
        url_model, 
        recent_clicks: List, 
        grpc_response_class, 
        grpc_click_info_class
    ):
        
        """Convert REST stats response to gRPC"""
        response = grpc_response_class()
        response.short_code = url_model.short_code
        response.original_url = url_model.original_url
        response.click_count = url_model.click_count
        response.created_at = int(url_model.created_at.timestamp())

        if url_model.expires_at:
            response.expires_at = int(url_model.expires_at.timestamp())

        # Recent clicks
        for click in recent_clicks:
            click_info = GrpcConverter.click_model_to_grpc_click_info(
                click, grpc_click_info_class
            )
            response.recent_clicks.append(click_info)

        return response
    
    @staticmethod
    def rest_to_list_response(
        urls: List, 
        total: int,
        grpc_response_class,
        grpc_url_info_class
    ):
        """Convert REST list response to gRPC"""
        response = grpc_response_class()
        response.total_count = total
        
        for url_model in urls:
            url_info = GrpcConverter.url_model_to_grpc_url_info(
                url_model, grpc_url_info_class
            )
            response.urls.append(url_info)
            
        return response
    
    @staticmethod
    class GrpcShortenUrlRequest(BaseModel):
        """Validation for gRPC URL shorting"""

        original_url: str
        custom_code: Optional[str] = None
        expires_in_days: Optional[int] = None

        class Config:
            validate_assignment = True

    class GrpcResolveUrlRequest(BaseModel):        
        short_code: str
        
        class Config:
            validate_assignment = True


    class GrpcGetStatsRequest(BaseModel):        
        short_code: str
        
        class Config:
            validate_assignment = True

    class GrpcListUrlsRequest(BaseModel):        
        limit: int = 20
        offset: int = 0
        
        def __post_init__(self):
            if self.limit > 100:
                self.limit = 100
            if self.limit < 1:
                self.limit = 1
            if self.offset < 0:
                self.offset = 0
        
        class Config:
            validate_assignment = True