import asyncio
from asyncua import Server, ua
from asyncua.ua import NodeId, NodeIdType
import argparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("opcua_server")

# Reduce verbosity of asyncua loggers
logging.getLogger("asyncua.server.uaprocessor").setLevel(logging.WARNING)
logging.getLogger("asyncua.server.subscription_service").setLevel(logging.WARNING)

class UserManager:
    def __init__(self, users):
        self.users = users

    async def user_manager(self, iserver, session, username, password):
        if username in self.users and self.users[username] == password:
            log.info(f"User {username} authenticated successfully")
            return True
        else:
            log.warning(f"User {username} authentication failed")
            return False

async def run_opcua_server(hostname, port, path, uri, users):
    # Set up OPC UA server
    server = Server()
    await server.init()
    endpoint = f"opc.tcp://{hostname}:{port}{path}"
    server.set_endpoint(endpoint)
    server.set_server_name("Python OPC UA Server")

    # Set up namespace
    idx = await server.register_namespace(uri)

    # Create Railway folder
    railway = await server.nodes.objects.add_folder(idx, "Railway")

    # Create Lights and Turnouts objects
    lights = await railway.add_object(NodeId(2001, idx, NodeIdType.Numeric), "Lights")
    turnouts = await railway.add_object(NodeId(2002, idx, NodeIdType.Numeric), "Turnouts")

    # Add variables to Turnouts
    left_turnout = await turnouts.add_variable(NodeId(2003, idx, NodeIdType.Numeric), "LeftTurnout", ua.Variant(0, ua.VariantType.Int64))
    right_turnout = await turnouts.add_variable(NodeId(2004, idx, NodeIdType.Numeric), "RightTurnout", ua.Variant(0, ua.VariantType.Int64))
    
    # Add variables to Lights
    left_lights = await lights.add_variable(NodeId(2005, idx, NodeIdType.Numeric), "LeftLights", ua.Variant(0, ua.VariantType.Int64))
    right_lights = await lights.add_variable(NodeId(2006, idx, NodeIdType.Numeric), "RightLights", ua.Variant(0, ua.VariantType.Int64))

    # Make variables writable
    await left_lights.set_writable()
    await right_lights.set_writable()
    await left_turnout.set_writable()
    await right_turnout.set_writable()

    # Log initialization
    log.info("Initialized variables and made them writable")

    # Set up user manager if users are provided
    if users:
        user_manager = UserManager(users)
        server.set_security_policy([ua.SecurityPolicyType.NoSecurity])  # Set security policy
        server.user_manager = user_manager.user_manager  # Directly assign the user_manager function
    else:
        log.info("No users provided, allowing anonymous connections")

    # Allow anonymous write if no users are provided
    if not users:
        server.allow_anonymous_write = True

    async with server:
        log.info(f"OPC UA Server started at {endpoint}")

        # Create a subscription to monitor data changes
        subscription = await server.create_subscription(100, DataChangeHandler())
        handles = []
        handles.append(await subscription.subscribe_data_change(left_lights))
        handles.append(await subscription.subscribe_data_change(right_lights))
        handles.append(await subscription.subscribe_data_change(left_turnout))
        handles.append(await subscription.subscribe_data_change(right_turnout))

        try:
            while True:
                await asyncio.sleep(1)
        finally:
            for handle in handles:
                await subscription.unsubscribe(handle)
            await subscription.delete()

class DataChangeHandler:
    def datachange_notification(self, node, val, data):
        log.info(f"Data change event: {node} = {val}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='OPC UA Server Script')
    parser.add_argument('--hostname', type=str, default='localhost', help='Hostname for the OPC UA server')
    parser.add_argument('--port', type=int, default=4840, help='Port for the OPC UA server')
    parser.add_argument('--path', type=str, default='/freeopcua/server/', help='Path for the OPC UA server endpoint')
    parser.add_argument('--uri', type=str, default='http://example.com', help='URI for the OPC UA namespace')
    parser.add_argument('--users', type=str, help='Comma-separated list of username:password pairs')

    args = parser.parse_args()

    # Parse users
    users = dict(user.split(":") for user in args.users.split(",")) if args.users else None

    asyncio.run(run_opcua_server(args.hostname, args.port, args.path, args.uri, users))
