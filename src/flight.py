import logging
import time
import json
import numpy as np
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
# from main import gui

# Specify the uri of the drone to which we want to connect (if your radio
# channel is X, the uri should be 'radio://0/X/2M/E7E7E7E7E7')
uri = 'radio://0/[channel]/2M/E7E7E7E7E7'

# Specify the variables we want to log (all at 100 Hz)
variables = [
    # State estimates (stock code)
    'ae483log.o_x',
    'ae483log.o_y',
    'ae483log.o_z',
    'ae483log.psi',
    'ae483log.theta',
    'ae483log.phi',
    'ae483log.v_x',
    'ae483log.v_y',
    'ae483log.v_z',
    # Measurements
    'ae483log.w_x',
    'ae483log.w_y',
    'ae483log.w_z',
    'ae483log.n_x',
    'ae483log.n_y',
    'ae483log.r',
    'ae483log.a_z',
    # Setpoint
    'ae483log.o_x_des',
    'ae483log.o_y_des',
    'ae483log.o_z_des',
    # Motor power commands
    'ae483log.m_1',
    'ae483log.m_2',
    'ae483log.m_3',
    'ae483log.m_4',
]


class SimpleClient:
    def __init__(self, use_controller=False, use_observer=False, channel=58):
        # Initialize everything
        logging.basicConfig(level=logging.ERROR)
        cflib.crtp.init_drivers()
        self.uri = uri.replace('[channel]', f'{channel}')
        self.init_time = time.time()
        self.use_controller = use_controller
        self.use_observer = use_observer
        self.cf = Crazyflie(rw_cache='./cache')
        self.cf.connected.add_callback(self.connected)
        self.cf.connection_failed.add_callback(self.connection_failed)
        self.cf.connection_lost.add_callback(self.connection_lost)
        self.cf.disconnected.add_callback(self.disconnected)
        print(f'Connecting to {self.uri}')
        self.cf.open_link(self.uri)
        self.is_connected = False
        self.data = {}
        # self.connect()
        
    def connect(self):
        while not self.is_connected:
            print(f' ... connecting ...')
            time.sleep(1.0)

    def connected(self, uri):
        print(f'Connected to {uri}')
        self.is_connected = True

        # Start logging
        self.logconfs = []
        self.logconfs.append(LogConfig(name=f'LogConf0', period_in_ms=10))
        num_variables = 0
        for v in variables:
            num_variables += 1
            if num_variables > 5: # <-- could increase if you paid attention to types / sizes (max 30 bytes per packet)
                num_variables = 0
                self.logconfs.append(LogConfig(name=f'LogConf{len(self.logconfs)}', period_in_ms=10))
            self.data[v] = {'time': [], 'data': []}
            self.logconfs[-1].add_variable(v)
        for logconf in self.logconfs:
            try:
                self.cf.log.add_config(logconf)
                logconf.data_received_cb.add_callback(self.log_data)
                logconf.error_cb.add_callback(self.log_error)
                logconf.start()
            except KeyError as e:
                print(f'Could not start {logconf.name} because {e}')
                for v in logconf.variables:
                    print(f' - {v.name}')
            except AttributeError:
                print(f'Could not start {logconf.name} because of bad configuration')
                for v in logconf.variables:
                    print(f' - {v.name}')

        # Reset the stock EKF
        self.cf.param.set_value('kalman.resetEstimation', 1)

        # Enable the controller (1 for stock controller, 4 for ae483 controller)
        if self.use_controller:
            self.cf.param.set_value('stabilizer.controller', 4)
        else:
            self.cf.param.set_value('stabilizer.controller', 1)

        # Enable the observer (0 for disable, 1 for enable)
        if self.use_observer:
            self.cf.param.set_value('ae483par.use_observer', 1)
        else:
            self.cf.param.set_value('ae483par.use_observer', 0)

    def connection_failed(self, uri, msg):
        print(f'Connection to {uri} failed: {msg}')

    def connection_lost(self, uri, msg):
        print(f'Connection to {uri} lost: {msg}')

    def disconnected(self, uri):
        print(f'Disconnected from {uri}')
        self.is_connected = False

    def log_data(self, timestamp, data, logconf):
        for v in logconf.variables:
            self.data[v.name]['time'].append(timestamp)
            self.data[v.name]['data'].append(data[v.name])

    def log_error(self, logconf, msg):
        print(f'Error when logging {logconf}: {msg}')

    def move(self, x, y, z, yaw, dt):
        print(f'Move to {x}, {y}, {z} with yaw {yaw} degrees for {dt} seconds')
        start_time = time.time()
        while time.time() - start_time < dt:
            self.cf.commander.send_position_setpoint(x, y, z, yaw)
            time.sleep(0.1)

    def move_smooth(self, p1, p2, yaw, dt):
        print(f'Move smoothly from {p1} to {p2} with yaw {yaw} degrees in {dt} seconds')
        p1 = np.array(p1)
        p2 = np.array(p2)
        start_time = time.time()
        while True:
            current_time = time.time()
            s = (current_time - start_time) / dt
            p = (1 - s) * p1 + (s * p2)
            self.cf.commander.send_position_setpoint(p[0], p[1], p[2], yaw)
            if s >= 1:
                return
            else:
                time.sleep(0.1)

    def stop(self, dt):
        print(f'Stop for {dt} seconds')
        self.cf.commander.send_stop_setpoint()
        start_time = time.time()
        while time.time() - start_time < dt:
            time.sleep(0.1)

    def disconnect(self):
        self.cf.close_link()

    def write_data(self, filename='logged_data.json'):
        with open(filename, 'w') as outfile:
            json.dump(self.data, outfile, indent=4, sort_keys=False)
        
    # TODO: Erika
    def get_coordinates(self):
        # call to the gui for translated coordinates
        coordinates = gui.runFlight()
        return coordinates
        
    # TODO: Erika
    def flight(self):
        # import runFlight from the GUI
        # loop through each tuple
        coordinates = self.get_coordinates()
        coordinates_len = len(coordinates)-1
        i = 0
        for tuple in coordinates:
            i += 1
            x = tuple[0]
            y = tuple[1]
            z = 0.5 # current constant
            client.move(x,y,z, 0, 0.02)
            # reach last tuple, set up to move back to 
            if i == coordinates_len:
                client.move_smooth([x,y,z], [0.0, 0.0, 0.0], 0.0, 6.0)
        # record normalized coordinates from GUI runFlight
        # maybe: real_coordinates = runFlight()
        
    def take_off(self):
        
        # Leave time at the start to initialize
        self.stop(1.0)

        # Take off and hover (with zero yaw)
        self.move(0.0, 0.0, 0.15, 0.0, 1.0)
        self.move(0.0, 0.0, 0.50, 0.0, 1.0)
        
    def land(self):
        
        # Go back to hover (with zero yaw) and prepare to land
        self.move(0.0, 0.0, 0.50, 0.0, 1.0)
        self.move(0.0, 0.0, 0.15, 0.0, 1.0)

        # Land
        self.stop(1.0)

        # Disconnect from drone
        self.disconnect()
        

if __name__ == '__main__':

    # Create and start the client that will connect to the drone
    client = SimpleClient(uri, use_controller=False, use_observer=False)
    
    # Leave time at the start to initialize
    client.stop(1.0)

    # Take off and hover (with zero yaw)
    # client.move(0.0, 0.0, 0.15, 0.0, 1.0)
    # client.move(0.0, 0.0, 0.50, 0.0, 1.0)

    # Fly in a square five times (with a pause at each corner)
    # num_squares = 5
    # for i in range(num_squares):
    #     client.move_smooth([0.0, 0.0, 0.5], [0.5, 0.0, 0.5], 0.0, 2.0)
    #     client.move(0.5, 0.0, 0.5, 0.0, 1.0)
    #     client.move_smooth([0.5, 0.0, 0.5], [0.5, 0.5, 0.5], 0.0, 2.0)
    #     client.move(0.5, 0.5, 0.5, 0.0, 1.0)
    #     client.move_smooth([0.5, 0.5, 0.5], [0.0, 0.5, 0.5], 0.0, 2.0)
    #     client.move(0.0, 0.5, 0.5, 0.0, 1.0)
    #     client.move_smooth([0.0, 0.5, 0.5], [0.0, 0.0, 0.5], 0.0, 2.0)
    #     client.move(0.0, 0.0, 0.5, 0.0, 1.0)

    # Go back to hover (with zero yaw) and prepare to land
    # client.move(0.0, 0.0, 0.50, 0.0, 1.0)
    # client.move(0.0, 0.0, 0.15, 0.0, 1.0)

    # Calling flight function with client move jazz from GUI
    client.flight()

    # Land
    client.stop(1.0)

    # Disconnect from drone
    client.disconnect()

    # Write data from flight
    client.write_data('hardware_data.json')
