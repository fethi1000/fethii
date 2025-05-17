from flask import Flask, request, render_template_string, jsonify
from collections import defaultdict

app = Flask(__name__)
devices = defaultdict(lambda: {'custom_name': None})

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>نظام تتبع الأجهزة</title>
    <style>
        body, html { margin: 0; padding: 0; height: 100%; font-family: Arial, sans-serif; }
        #map { height: 100vh; width: 100%; }
        #control-panel {
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
            width: 300px;
        }
        .device-label {
            font-weight: bold;
            background: white;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid #ddd;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-top: -35px !important;
        }
        #rename-form {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #eee;
        }
    </style>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
</head>
<body>
    <div id="map"></div>
    <div id="control-panel">
        <h2 style="margin-top: 0;">إدارة الأجهزة</h2>
        <div id="device-list"></div>
        <div id="rename-form">
            <h3>تغيير اسم الجهاز:</h3>
            <select id="device-select" style="width: 100%; padding: 8px; margin-bottom: 10px;">
                <option value="">اختر جهازاً</option>
            </select>
            <input type="text" id="new-name" placeholder="الاسم الجديد" style="width: 100%; padding: 8px; margin-bottom: 10px;">
            <button onclick="renameDevice()" style="width: 100%; padding: 10px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">
                تغيير الاسم
            </button>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        let map;
        const deviceMarkers = {};
        const deviceLabels = {};
        
        function initMap() {
            map = L.map('map').setView([35.389062, -1.0950887], 15);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
            updateDevices();
        }
        
        function updateDevices() {
            fetch('/get_devices')
                .then(response => response.json())
                .then(devices => {
                    Object.values(deviceMarkers).forEach(marker => map.removeLayer(marker));
                    Object.values(deviceLabels).forEach(label => map.removeLayer(label));
                    updateDeviceList(devices);
                    for (const [deviceId, deviceData] of Object.entries(devices)) {
                        if (deviceData.lat && deviceData.lon) {
                            const displayName = deviceData.custom_name || deviceId;
                            deviceMarkers[deviceId] = L.marker([deviceData.lat, deviceData.lon])
                                .addTo(map)
                                .bindPopup(`<b>${displayName}</b><br>الإحداثيات: ${deviceData.lat}, ${deviceData.lon}`);
                            deviceLabels[deviceId] = L.marker([deviceData.lat, deviceData.lon], {
                                icon: L.divIcon({
                                    className: 'device-label',
                                    html: displayName,
                                    iconSize: [120, 20]
                                })
                            }).addTo(map);
                        }
                    }
                });
        }
        
        function updateDeviceList(devices) {
            const deviceList = document.getElementById('device-list');
            const deviceSelect = document.getElementById('device-select');
            deviceList.innerHTML = '';
            deviceSelect.innerHTML = '<option value="">اختر جهازاً</option>';
            for (const [deviceId, deviceData] of Object.entries(devices)) {
                const displayName = deviceData.custom_name || deviceId;
                const item = document.createElement('div');
                item.textContent = displayName;
                item.style.padding = '8px';
                item.style.cursor = 'pointer';
                item.style.borderBottom = '1px solid #eee';
                item.onclick = () => {
                    map.setView([deviceData.lat, deviceData.lon], 18);
                    deviceMarkers[deviceId].openPopup();
                };
                deviceList.appendChild(item);
                const option = document.createElement('option');
                option.value = deviceId;
                option.textContent = displayName;
                deviceSelect.appendChild(option);
            }
        }
        
        function renameDevice() {
            const deviceId = document.getElementById('device-select').value;
            const newName = document.getElementById('new-name').value.trim();
            if (!deviceId || !newName) {
                alert('الرجاء اختيار جهاز وإدخال اسم جديد');
                return;
            }
            fetch('/rename_device', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device_id: deviceId, new_name: newName })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('تم تغيير الاسم بنجاح');
                    document.getElementById('new-name').value = '';
                    updateDevices();
                } else {
                    alert('حدث خطأ: ' + data.message);
                }
            });
        }

        document.addEventListener('DOMContentLoaded', () => {
            initMap();
            setInterval(updateDevices, 3000);
        });
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def handle_requests():
    if request.method == 'POST':
        return update_device()
    return render_template_string(HTML_TEMPLATE)

@app.route('/update', methods=['GET', 'POST'])
def update_device():
    try:
        data = request.get_json(silent=True) or request.form or request.args
        device_id = data.get('id')
        lat = data.get('lat')
        lon = data.get('lon')
        if not all([device_id, lat, lon]):
            return jsonify({'status': 'error', 'message': 'يجب إرسال معرف الجهاز والإحداثيات'}), 400
        if devices[device_id]['custom_name'] is None:
            devices[device_id]['custom_name'] = device_id
        devices[device_id].update({
            'lat': float(lat),
            'lon': float(lon),
            'timestamp': data.get('timestamp'),
            'battery': data.get('batt'),
            'speed': data.get('speed'),
            'accuracy': data.get('accuracy')
        })
        print(f"تم تحديث بيانات الجهاز {device_id}: ({lat}, {lon})")
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"خطأ في معالجة البيانات: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/rename_device', methods=['POST'])
def rename_device():
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        new_name = data.get('new_name')
        if not device_id or not new_name:
            return jsonify({'success': False, 'message': 'بيانات ناقصة'}), 400
        if device_id in devices:
            devices[device_id]['custom_name'] = new_name
            print(f"تم تغيير اسم الجهاز {device_id} إلى {new_name}")
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'الجهاز غير موجود'}), 404
    except Exception as e:
        print(f"خطأ في تغيير الاسم: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ في الخادم'}), 500

@app.route('/get_devices', methods=['GET'])
def get_devices():
    return jsonify(devices)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

