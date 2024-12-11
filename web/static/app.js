// web/static/app.js
const { useState, useEffect } = React;
const { LineChart, BarChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } = Recharts;

function IMUDisplay() {
    const [data, setData] = useState([]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await fetch('/api/imu');
                const newData = await response.json();
                setData(newData);
            } catch (error) {
                console.error('Error fetching IMU data:', error);
            }
        };

        // Update every 200ms (5Hz)
        const interval = setInterval(fetchData, 200);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="p-4 bg-gray-50 rounded-lg shadow-lg m-4">
            <h1 className="text-2xl font-bold mb-4 text-gray-800">Excavator IMU Data</h1>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Accelerometer Chart */}
                <div className="bg-white p-4 rounded-lg shadow">
                    <h2 className="text-xl font-semibold mb-2">Accelerometer Data (m/s²)</h2>
                    <BarChart width={500} height={300} data={data}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Bar dataKey="accel_x" fill="#8884d8" name="X-Axis" />
                        <Bar dataKey="accel_y" fill="#82ca9d" name="Y-Axis" />
                        <Bar dataKey="accel_z" fill="#ffc658" name="Z-Axis" />
                    </BarChart>
                </div>

                {/* Gyroscope Chart */}
                <div className="bg-white p-4 rounded-lg shadow">
                    <h2 className="text-xl font-semibold mb-2">Gyroscope Data (rad/s)</h2>
                    <LineChart width={500} height={300} data={data}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="gyro_x" stroke="#8884d8" name="X-Axis" />
                        <Line type="monotone" dataKey="gyro_y" stroke="#82ca9d" name="Y-Axis" />
                        <Line type="monotone" dataKey="gyro_z" stroke="#ffc658" name="Z-Axis" />
                    </LineChart>
                </div>

                {/* IMU Status Cards */}
                <div className="col-span-full grid grid-cols-1 md:grid-cols-3 gap-4">
                    {data.map((imu) => (
                        <div key={imu.name} className="bg-white p-4 rounded-lg shadow">
                            <h3 className="text-lg font-semibold mb-2">{imu.name}</h3>
                            <div className="grid grid-cols-2 gap-2 text-sm">
                                <div>
                                    <p className="font-medium">Accelerometer:</p>
                                    <p>X: {imu.accel_x.toFixed(3)}</p>
                                    <p>Y: {imu.accel_y.toFixed(3)}</p>
                                    <p>Z: {imu.accel_z.toFixed(3)}</p>
                                </div>
                                <div>
                                    <p className="font-medium">Gyroscope:</p>
                                    <p>X: {imu.gyro_x.toFixed(3)}</p>
                                    <p>Y: {imu.gyro_y.toFixed(3)}</p>
                                    <p>Z: {imu.gyro_z.toFixed(3)}</p>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

ReactDOM.render(React.createElement(IMUDisplay), document.getElementById('root'));
