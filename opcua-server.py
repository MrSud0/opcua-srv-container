import asyncio
from asyncua import Server, ua
from asyncua.common.methods import uamethod
from asyncua.common.structures104 import new_struct, new_struct_field
from asyncua.server.users import UserRole, User
import argparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("opcua_server")

# Reduce verbosity of asyncua loggers
logging.getLogger("asyncua.server.uaprocessor").setLevel(logging.WARNING)
logging.getLogger("asyncua.server.subscription_service").setLevel(logging.WARNING)

class CustomUserManager:
    def __init__(self, users):
        self.users = users

    def get_user(self, iserver, username=None, password=None, certificate=None):
        # Authenticate based on the username and password
        if username in self.users and self.users[username] == password:
            log.info(f"User {username} authenticated successfully")
            return User(role=UserRole.User)  # Returning User role for authenticated users
        log.warning(f"User {username} authentication failed")
        return None

async def run_opcua_server(hostname, port, path, uri, users):
    # Initialize custom user manager with the provided users
    user_manager = CustomUserManager(users)
    
    # Set up OPC UA server with custom user manager
    server = Server(user_manager=user_manager)
    await server.init()
    endpoint = f"opc.tcp://{hostname}:{port}{path}"
    server.set_endpoint(endpoint)
    server.set_server_name("Python OPC UA Server")

    # Set up namespace
    idx = await server.register_namespace(uri)

    # Create Railway folder
    railway = await server.nodes.objects.add_folder(idx, "Railway")

    # Create Lights and Turnouts objects
    lights = await railway.add_object(ua.NodeId(2000, idx), "Lights")
    turnouts = await railway.add_object(ua.NodeId(2001, idx), "Turnouts")

    dev_var = await turnouts.add_variable(ua.NodeId(2002, idx), "DevVar", ua.Variant(0, ua.VariantType.Int64))
    await dev_var.set_writable()

    # Add variables to Turnouts with read and write access
    left_turnout = await turnouts.add_variable(ua.NodeId(2003, idx), "LeftTurnout", ua.Variant(0, ua.VariantType.Int64))
    await left_turnout.set_writable()
    right_turnout = await turnouts.add_variable(ua.NodeId(2004, idx), "RightTurnout", ua.Variant(0, ua.VariantType.Int64))
    await right_turnout.set_writable()

    # Add variables to Lights with read and write access
    left_lights = await lights.add_variable(ua.NodeId(2005, idx), "LeftLights", ua.Variant(0, ua.VariantType.Int64))
    await left_lights.set_writable()
    right_lights = await lights.add_variable(ua.NodeId(2006, idx), "RightLights", ua.Variant(0, ua.VariantType.Int64))
    await right_lights.set_writable()

    async with server:
        log.info(f"OPC UA Server started at {endpoint}")

        # Create a subscription to monitor data changes
        subscription = await server.create_subscription(100, None)

        async def subscribe_node(node):
            handle = await subscription.subscribe_data_change(node)
            return handle

        handles = []
        handles.append(await subscribe_node(dev_var))
        handles.append(await subscribe_node(left_lights))
        handles.append(await subscribe_node(right_lights))
        handles.append(await subscribe_node(left_turnout))
        handles.append(await subscribe_node(right_turnout))

        try:
            while True:
                await asyncio.sleep(1)
        finally:
            for handle in handles:
                await subscription.unsubscribe(handle)
            await subscription.delete()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='OPC UA Server Script')
    parser.add_argument('--hostname', type=str, default='localhost', help='Hostname for the OPC UA server')
    parser.add_argument('--port', type=int, default=4840, help='Port for the OPC UA server')
    parser.add_argument('--path', type=str, default='/railway/', help='Path for the OPC UA server endpoint')
    parser.add_argument('--uri', type=str, default='http://railwaycorp.eu', help='URI for the OPC UA namespace')
    parser.add_argument('--users', type=str, help='Comma-separated list of username:password pairs')

    args = parser.parse_args()

    # Parse users
    users = dict(user.split(":") for user in args.users.split(",")) if args.users else None

    asyncio.run(run_opcua_server(args.hostname, args.port, args.path, args.uri, users))
