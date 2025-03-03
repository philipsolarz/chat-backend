#!/usr/bin/env python
# Payment service for handling subscriptions and purchases
from typing import Dict, Any, Optional, List, Tuple

from client.api.base_service import BaseService, APIError
from client.game.state import game_state
from client.ui.console import console

class PaymentService(BaseService):
    """Service for payment-related API operations"""
    
    async def get_subscription_plans(self) -> List[Dict[str, Any]]:
        """Get available subscription plans"""
        try:
            response = await self.get("/payments/plans")
            return response or []
        except APIError as e:
            console.print(f"[red]Failed to get subscription plans: {e.detail}[/red]")
            return []
        except Exception as e:
            console.print(f"[red]Error getting subscription plans: {str(e)}[/red]")
            return []
    
    async def get_subscription_info(self) -> Dict[str, Any]:
        """Get current user's subscription information"""
        try:
            response = await self.get("/payments/subscription")
            return response or {"is_premium": False, "subscription": None}
        except APIError as e:
            console.print(f"[red]Failed to get subscription info: {e.detail}[/red]")
            return {"is_premium": False, "subscription": None}
        except Exception as e:
            console.print(f"[red]Error getting subscription info: {str(e)}[/red]")
            return {"is_premium": False, "subscription": None}
    
    async def create_subscription_checkout(self, plan_id: str, 
                                         success_url: str = "http://localhost:3000/success", 
                                         cancel_url: str = "http://localhost:3000/cancel") -> Optional[Dict[str, str]]:
        """Create a checkout session for subscription purchase"""
        try:
            payload = {
                "plan_id": plan_id,
                "success_url": success_url,
                "cancel_url": cancel_url
            }
            
            response = await self.post("/payments/checkout", payload)
            return response
        except APIError as e:
            console.print(f"[red]Failed to create checkout session: {e.detail}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error creating checkout session: {str(e)}[/red]")
            return None
    
    async def create_billing_portal(self, return_url: str = "http://localhost:3000/account") -> Optional[Dict[str, str]]:
        """Create a billing portal session for managing subscription"""
        try:
            payload = {
                "return_url": return_url
            }
            
            response = await self.post("/payments/billing-portal", payload)
            return response
        except APIError as e:
            console.print(f"[red]Failed to create billing portal: {e.detail}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error creating billing portal: {str(e)}[/red]")
            return None
    
    async def cancel_subscription(self) -> bool:
        """Cancel the current subscription"""
        try:
            await self.post("/payments/subscription/cancel", {})
            return True
        except APIError as e:
            console.print(f"[red]Failed to cancel subscription: {e.detail}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error canceling subscription: {str(e)}[/red]")
            return False
    
    async def create_zone_tier_upgrade_checkout(self, zone_id: str,
                                             success_url: str = "http://localhost:3000/success",
                                             cancel_url: str = "http://localhost:3000/cancel") -> Optional[Dict[str, str]]:
        """Create a checkout session for zone tier upgrade"""
        try:
            payload = {
                "zone_id": zone_id,
                "success_url": success_url,
                "cancel_url": cancel_url
            }
            
            response = await self.post("/zones/tier-upgrade-checkout", payload)
            return response
        except APIError as e:
            console.print(f"[red]Failed to create zone upgrade checkout: {e.detail}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error creating zone upgrade checkout: {str(e)}[/red]")
            return None
    
    async def create_world_tier_upgrade_checkout(self, world_id: str,
                                              success_url: str = "http://localhost:3000/success",
                                              cancel_url: str = "http://localhost:3000/cancel") -> Optional[Dict[str, str]]:
        """Create a checkout session for world tier upgrade"""
        try:
            payload = {
                "world_id": world_id,
                "success_url": success_url,
                "cancel_url": cancel_url
            }
            
            response = await self.post("/worlds/tier-upgrade-checkout", payload)
            return response
        except APIError as e:
            console.print(f"[red]Failed to create world upgrade checkout: {e.detail}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error creating world upgrade checkout: {str(e)}[/red]")
            return None
    
    async def create_entity_tier_upgrade_checkout(self, entity_id: str,
                                               success_url: str = "http://localhost:3000/success",
                                               cancel_url: str = "http://localhost:3000/cancel") -> Optional[Dict[str, str]]:
        """Create a checkout session for entity tier upgrade"""
        try:
            # Entity upgrades use query parameters
            params = {
                "success_url": success_url,
                "cancel_url": cancel_url
            }
            
            response = await self.post(f"/entities/{entity_id}/upgrade-tier", params=params)
            return response
        except APIError as e:
            console.print(f"[red]Failed to create entity upgrade checkout: {e.detail}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error creating entity upgrade checkout: {str(e)}[/red]")
            return None