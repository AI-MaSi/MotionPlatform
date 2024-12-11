const { useState, useEffect } = React;
const { LineChart, BarChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } = Recharts;

function IMUDisplay() {
    const [data, setData] = useState([
        {name: 'IMU_0', accel_x: 0, accel_y: 0, accel_z: 0, gyro_x: 0, gyro_y: 0, gyro_z: 0},
        {name: 'IMU_1', accel_x: 0, accel_y: 0, accel_z: 0, gyro_x: 0, gyro_y: 0, gyro_z: 0},
        {name: 'IMU_2', accel_x: 0, accel_y: 0, accel_z: 0, gyro_x: 0, gyro_y: 0, gyro_z: 0}
    ]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await fetch('/api/imu');
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                const newData = await response.json();
                setData(newData);
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        };

        const interval = setInterval(fetchData, 200);
        return () => clearInterval(interval);
    }, []);

    return React.createElement('div', { className: 'p-4 bg-gray-100' },
        // Title
        React.createElement('h1', { className: 'text-2xl font-bold mb-4' }, 'IMU Data Visualization'),

        // Cards Grid
        React.createElement('div', { className: 'grid grid-cols-1 md:grid-cols-3 gap-4 mb-8' },
            data.map(imu =>
                React.createElement('div', {
                    key: imu.name,
                    className: 'bg-white p-4 rounded-lg shadow-lg'
                },
                    React.createElement('h3', { className: 'text-lg font-bold mb-3' }, imu.name),
                    React.createElement('div', { className: 'grid grid-cols-2 gap-4' },
                        React.createElement('div', null,
                            React.createElement('p', { className: 'font-medium text-blue-600' }, 'Accelerometer:'),
                            React.createElement('p', null, `X: ${imu.accel_x?.toFixed(3)}`),
                            React.createElement('p', null, `Y: ${imu.accel_y?.toFixed(3)}`),
                            React.createElement('p', null, `Z: ${imu.accel_z?.toFixed(3)}`)
                        ),
                        React.createElement('div', null,
                            React.createElement('p', { className: 'font-medium text-green-600' }, 'Gyroscope:'),
                            React.createElement('p', null, `X: ${imu.gyro_x?.toFixed(3)}`),
                            React.createElement('p', null, `Y: ${imu.gyro_y?.toFixed(3)}`),
                            React.createElement('p', null, `Z: ${imu.gyro_z?.toFixed(3)}`)
                        )
                    )
                )
            )
        ),

        // Charts Container
        React.createElement('div', { className: 'grid grid-cols-1 gap-8' },
            // Accelerometer Chart
            React.createElement('div', { className: 'bg-white p-4 rounded-lg shadow-lg' },
                React.createElement('h2', { className: 'text-xl font-semibold mb-4' }, 'Accelerometer Data (m/s²)'),
                React.createElement('div', { style: { width: '100%', height: '400px' } },
                    React.createElement(ResponsiveContainer, null,
                        React.createElement(BarChart, { data: data },
                            React.createElement(CartesianGrid, { strokeDasharray: '3 3' }),
                            React.createElement(XAxis, { dataKey: 'name' }),
                            React.createElement(YAxis),
                            React.createElement(Tooltip),
                            React.createElement(Legend),
                            React.createElement(Bar, { dataKey: 'accel_x', fill: '#8884d8', name: 'X-Axis' }),
                            React.createElement(Bar, { dataKey: 'accel_y', fill: '#82ca9d', name: 'Y-Axis' }),
                            React.createElement(Bar, { dataKey: 'accel_z', fill: '#ffc658', name: 'Z-Axis' })
                        )
                    )
                )
            ),

            // Gyroscope Chart
            React.createElement('div', { className: 'bg-white p-4 rounded-lg shadow-lg' },
                React.createElement('h2', { className: 'text-xl font-semibold mb-4' }, 'Gyroscope Data (rad/s)'),
                React.createElement('div', { style: { width: '100%', height: '400px' } },
                    React.createElement(ResponsiveContainer, null,
                        React.createElement(LineChart, { data: data },
                            React.createElement(CartesianGrid, { strokeDasharray: '3 3' }),
                            React.createElement(XAxis, { dataKey: 'name' }),
                            React.createElement(YAxis),
                            React.createElement(Tooltip),
                            React.createElement(Legend),
                            React.createElement(Line, { type: 'monotone', dataKey: 'gyro_x', stroke: '#8884d8', name: 'X-Axis' }),
                            React.createElement(Line, { type: 'monotone', dataKey: 'gyro_y', stroke: '#82ca9d', name: 'Y-Axis' }),
                            React.createElement(Line, { type: 'monotone', dataKey: 'gyro_z', stroke: '#ffc658', name: 'Z-Axis' })
                        )
                    )
                )
            )
        )
    );
}

// Initialize React app
const root = document.getElementById('root');
ReactDOM.render(React.createElement(IMUDisplay), root);