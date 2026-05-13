from __future__ import annotations

from lxml import etree

MALMO_NS = "http://ProjectMalmo.microsoft.com"
MALMO_VERSION = "0.37.0"


def build_mission_init(mission_xml: str, *, episode_id: str, role: int = 0) -> bytes:
    """Wrap a Mission XML document in the MissionInit envelope expected by Malmo."""
    mission = etree.fromstring(mission_xml.encode("utf-8"))
    mission_init = etree.fromstring(
        f"""
        <MissionInit xmlns="{MALMO_NS}"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            SchemaVersion="" PlatformVersion="{MALMO_VERSION}">
            <ExperimentUID>{episode_id}</ExperimentUID>
            <ClientRole>{role}</ClientRole>
            <ClientAgentConnection>
                <ClientIPAddress>127.0.0.1</ClientIPAddress>
                <ClientMissionControlPort>0</ClientMissionControlPort>
                <ClientCommandsPort>0</ClientCommandsPort>
                <AgentIPAddress>127.0.0.1</AgentIPAddress>
                <AgentMissionControlPort>0</AgentMissionControlPort>
                <AgentVideoPort>0</AgentVideoPort>
                <AgentDepthPort>0</AgentDepthPort>
                <AgentLuminancePort>0</AgentLuminancePort>
                <AgentObservationsPort>0</AgentObservationsPort>
                <AgentRewardsPort>0</AgentRewardsPort>
                <AgentColourMapPort>0</AgentColourMapPort>
            </ClientAgentConnection>
        </MissionInit>
        """.encode("utf-8")
    )
    mission_init.insert(0, mission)
    return etree.tostring(mission_init)
