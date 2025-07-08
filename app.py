from flask import Flask, request, render_template_string, jsonify
from collections import defaultdict
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

# تعريف وقت انتهاء صلاحية الإشارة (دقيقة واحدة)
INACTIVE_THRESHOLD = timedelta(minutes=1)
devices = defaultdict(lambda: {'custom_name': None, 'last_update': None})

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>نظام تتبع الأجهزة</title>
<style>
  body, html { margin:0; padding:0; height:100%; font-family: Arial, sans-serif; }
  #map { height:100vh; width:100%; }
  #control-panel, #device-names-panel {
      position: absolute; 
      top: 60px; 
      right: 10px;
      z-index: 1100;
      background: rgba(255,255,255,0.97);
      padding: 15px; 
      border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.2);
      width: 260px; 
      display: none;
      max-height: 80vh;
      overflow-y: auto;
  }
  .device-label-container {
      position: absolute;
      transform: translate(-50%, -100%);
      text-align: center;
      z-index: 1000;
  }
  .device-label {
      font-weight: bold;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 12px;
      white-space: nowrap;
      color: white;
      text-align: center;
      border: 1px solid #ddd;
      box-shadow: 0 1px 2px rgba(0,0,0,0.07);
      display: inline-block;
      user-select: none;
      margin-bottom: 5px;
  }
  .device-label.active {
      background-color: #28a745;
  }
  .device-label.inactive {
      background-color: #dc3545;
  }
  #rename-form {
      margin-top: 15px;
      padding-top: 15px;
      border-top: 1px solid #eee;
  }
  #admin-btn, #show-names-btn, #locate-me-btn {
      position: absolute;
      top: 10px;
      z-index: 1200;
      padding: 6px 14px;
      font-size: 14px;
      border-radius: 4px;
      border: none;
      background-color: #007bff;
      color: white;
      cursor: pointer;
      user-select: none;
  }
  #admin-btn { right: 10px; }
  #show-names-btn { right: 140px; background: #28a745; }
  #locate-me-btn { right: 270px; background: #ffc107; color: #000; }
  #passcode-popup {
      display: none;
      position: absolute;
      top: 50px;
      right: 10px;
      z-index: 1300;
      background: rgba(255,255,255,0.98);
      padding: 15px;
      border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.2);
      width: 260px;
  }
  .device-list-item {
      padding: 8px;
      cursor: pointer;
      border-bottom: 1px solid #eee;
      display: flex;
      justify-content: space-between;
      align-items: center;
      transition: background-color 0.2s;
  }
  .device-list-item:hover {
      background-color: #f5f5f5;
  }
  .device-list-item.active {
      color: #000;
  }
  .device-list-item.inactive {
      color: #dc3545;
  }
  .delete-btn {
      background: #dc3545;
      color: white;
      border: none;
      border-radius: 4px;
      padding: 4px 8px;
      cursor: pointer;
      font-size: 12px;
  }
  .button-group {
      display: flex;
      gap: 10px;
      margin-top: 10px;
  }
  .button-group button {
      flex: 1;
      padding: 10px;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      color: white;
  }
  .user-location-marker {
      background-color: #4285F4;
      border-radius: 50%;
      border: 2px solid white;
      width: 20px !important;
      height: 20px !important;
      box-shadow: 0 2px 5px rgba(0,0,0,0.3);
  }
  #permission-popup {
      display: none;
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      z-index: 2000;
      background: white;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.2);
      text-align: center;
      max-width: 80%;
  }
</style>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"/>
</head>
<body>
<div id="map"></div>
<button id="admin-btn"><i class="fas fa-cog"></i> إدارة الأجهزة</button>
<button id="show-names-btn"><i class="fas fa-list"></i> عرض أسماء الأجهزة</button>
<button id="locate-me-btn"><i class="fas fa-location-arrow"></i> موقعي الحالي</button>

<!-- نافذة طلب إذن الوصول إلى الموقع -->
<div id="permission-popup">
    <h3>السماح بالوصول إلى موقعك</h3>
    <p>يحتاج التطبيق إلى إذن للوصول إلى موقعك الحالي لتحديده على الخريطة.</p>
    <div class="button-group">
        <button id="grant-permission-btn" style="background: #28a745;">السماح</button>
        <button id="deny-permission-btn" style="background: #dc3545;">رفض</button>
    </div>
</div>

<div id="passcode-popup">
    <button class="close-passcode" onclick="document.getElementById('passcode-popup').style.display='none'">×</button>
    <label for="passcode-input" style="display:block; margin-bottom:8px;">أدخل كود الدخول:</label>
    <input type="password" id="passcode-input" style="width: 100%; padding: 8px; margin-bottom: 10px;" placeholder="كود الدخول" />
    <button id="passcode-submit" style="
        width: 100%;
        padding: 10px;
        background: #28a745;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    "><i class="fas fa-sign-in-alt"></i> دخول</button>
    <div id="passcode-error" style="color: red; margin-top: 8px; display: none;">كود غير صحيح</div>
</div>

<div id="control-panel">
    <h2>
        <i class="fas fa-cogs"></i> إدارة الأجهزة
        <button id="close-control" style="float: left; background: #dc3545; color: white; border: none; border-radius: 4px; padding: 4px 8px; cursor: pointer;"><i class="fas fa-times"></i> إغلاق</button>
    </h2>
    <div id="device-list"></div>
    <div id="rename-form">
        <h3><i class="fas fa-edit"></i> إدارة اسم الجهاز:</h3>
        <select id="device-select" style="width: 100%; padding: 8px; margin-bottom: 10px;">
            <option value="">اختر جهازاً</option>
        </select>
        <input type="text" id="new-name" placeholder="الاسم الجديد" style="width: 100%; padding: 8px; margin-bottom: 10px;" />
        <div class="button-group">
            <button onclick="renameDevice()" style="background: #4CAF50;">
                <i class="fas fa-save"></i> تغيير الاسم
            </button>
            <button onclick="deleteDevice()" style="background: #dc3545;">
                <i class="fas fa-trash"></i> حذف الجهاز
            </button>
        </div>
    </div>
</div>

<div id="device-names-panel">
    <h3 style="margin-top: 0;"><i class="fas fa-list-ol"></i> أسماء الأجهزة</h3>
    <div id="device-names-list"></div>
    <button onclick="document.getElementById('device-names-panel').style.display='none';" style="margin-top:10px;width:100%;padding:8px;background:#dc3545;color:white;border:none;border-radius:4px;cursor:pointer;">
        <i class="fas fa-times"></i> إغلاق
    </button>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js"></script>
<script>
    let map;
    const deviceMarkers = {};
    const deviceLabels = {};
    let userLocationMarker = null;
    let watchId = null;
    let isAndroidApp = false;

    // اكتشاف إذا كان التطبيق يعمل داخل WebView في Android
    function detectAndroidApp() {
        const userAgent = navigator.userAgent || navigator.vendor || window.opera;
        return /android/i.test(userAgent) && /wv|webview/i.test(userAgent.toLowerCase());
    }

    function formatDateTime(dateStr) {
        if (!dateStr) return 'غير متوفر';
        
        try {
            const date = new Date(dateStr);
            if (isNaN(date.getTime())) return 'تاريخ غير صالح';
            
            const day = String(date.getDate()).padStart(2, '0');
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const year = date.getFullYear();
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            const seconds = String(date.getSeconds()).padStart(2, '0');
            
            return `${day}/${month}/${year} - ${hours}:${minutes}:${seconds}`;
        } catch (e) {
            console.error('Error formatting date:', e);
            return 'تاريخ غير صالح';
        }
    }

    function isDeviceActive(deviceData) {
        if (!deviceData.last_update) return false;
        const lastUpdate = new Date(deviceData.last_update);
        const now = new Date();
        return (now - lastUpdate) < (1 * 60 * 1000); // 1 دقيقة
    }

    function initMap() {
        map = L.map('map').setView([35.389062, -1.0950887], 15);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
        updateDevices();
        
        // اكتشاف إذا كان التطبيق يعمل داخل WebView في Android
        isAndroidApp = detectAndroidApp();
        console.log('Is Android WebView:', isAndroidApp);
    }

    function createLabel(deviceId, deviceData, isActive) {
        const displayName = deviceData.custom_name || deviceId;
        const labelContainer = L.divIcon({
            className: 'device-label-container',
            html: `<div class="device-label ${isActive ? 'active' : 'inactive'}">${displayName}</div>`,
            iconSize: [0, 0],
            iconAnchor: [0, 0]
        });
        
        return L.marker([deviceData.lat, deviceData.lon], {
            icon: labelContainer,
            interactive: false
        });
    }

    function updateDevices() {
        fetch('/get_devices')
            .then(response => response.json())
            .then(devices => {
                for (const deviceId in deviceMarkers) {
                    if (!devices[deviceId]) {
                        map.removeLayer(deviceMarkers[deviceId]);
                        map.removeLayer(deviceLabels[deviceId]);
                        delete deviceMarkers[deviceId];
                        delete deviceLabels[deviceId];
                    }
                }

                updateDeviceList(devices);
                updateDeviceNamesList(devices);

                for (const [deviceId, deviceData] of Object.entries(devices)) {
                    if (deviceData.lat && deviceData.lon) {
                        const isActive = isDeviceActive(deviceData);
                        const displayName = deviceData.custom_name || deviceId;
                        const lastUpdate = formatDateTime(deviceData.last_update);
                        
                        if (!deviceMarkers[deviceId]) {
                            deviceMarkers[deviceId] = L.marker([deviceData.lat, deviceData.lon])
                                .addTo(map)
                                .bindPopup(`<b>${displayName}</b><br>آخر تحديث: ${lastUpdate}`);
                            
                            deviceLabels[deviceId] = createLabel(deviceId, deviceData, isActive).addTo(map);
                        } else {
                            deviceMarkers[deviceId].setLatLng([deviceData.lat, deviceData.lon]);
                            deviceMarkers[deviceId].getPopup().setContent(`<b>${displayName}</b><br>آخر تحديث: ${lastUpdate}`);
                            
                            map.removeLayer(deviceLabels[deviceId]);
                            deviceLabels[deviceId] = createLabel(deviceId, deviceData, isActive).addTo(map);
                        }
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
            const isActive = isDeviceActive(deviceData);
            
            const item = document.createElement('div');
            item.className = 'device-list-item ' + (isActive ? 'active' : 'inactive');
            item.innerHTML = `
                <span>${displayName}</span>
                <button class="delete-btn" onclick="event.stopPropagation(); confirmDeleteDevice('${deviceId}')">
                    <i class="fas fa-trash"></i>
                </button>
            `;
            item.onclick = () => {
                if (deviceData.lat && deviceData.lon) {
                    map.setView([deviceData.lat, deviceData.lon], 18);
                    if (deviceMarkers[deviceId]) deviceMarkers[deviceId].openPopup();
                }
            };
            deviceList.appendChild(item);
            
            const option = document.createElement('option');
            option.value = deviceId;
            option.textContent = displayName;
            deviceSelect.appendChild(option);
        }
    }

    function updateDeviceNamesList(devices) {
        const deviceNamesList = document.getElementById('device-names-list');
        deviceNamesList.innerHTML = '';
        
        for (const [deviceId, deviceData] of Object.entries(devices)) {
            const displayName = deviceData.custom_name || deviceId;
            const isActive = isDeviceActive(deviceData);
            
            const item = document.createElement('div');
            item.className = 'device-list-item ' + (isActive ? 'active' : 'inactive');
            item.textContent = displayName;
            
            item.onclick = function() {
                if (deviceData.lat && deviceData.lon) {
                    map.setView([deviceData.lat, deviceData.lon], 18);
                    if (deviceMarkers[deviceId]) {
                        deviceMarkers[deviceId].openPopup();
                    }
                }
            };
            
            deviceNamesList.appendChild(item);
        }
        
        if (Object.keys(devices).length === 0) {
            deviceNamesList.innerHTML = '<div style="color:#888;text-align:center;">لا توجد أجهزة</div>';
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

    function confirmDeleteDevice(deviceId) {
        const deviceData = devices[deviceId];
        const displayName = deviceData?.custom_name || deviceId;
        
        if (!confirm(`هل أنت متأكد من حذف الجهاز "${displayName}"؟ هذا الإجراء لا يمكن التراجع عنه.`)) {
            return;
        }
        
        deleteDevice(deviceId);
    }

    function deleteDevice(deviceId = null) {
        if (!deviceId) {
            deviceId = document.getElementById('device-select').value;
        }
        
        if (!deviceId) {
            alert('الرجاء اختيار جهاز للحذف');
            return;
        }
        
        fetch('/delete_device', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_id: deviceId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // حذف العلامة من الخريطة فوراً
                if (deviceMarkers[deviceId]) {
                    map.removeLayer(deviceMarkers[deviceId]);
                    map.removeLayer(deviceLabels[deviceId]);
                    delete deviceMarkers[deviceId];
                    delete deviceLabels[deviceId];
                }
                
                alert('تم حذف الجهاز بنجاح');
                updateDevices();
            } else {
                alert('حدث خطأ: ' + data.message);
            }
        })
        .catch(error => {
            alert('حدث خطأ في الاتصال بالخادم');
            console.error('Error:', error);
        });
    }

    function requestLocationPermission() {
        return new Promise((resolve, reject) => {
            if (!isAndroidApp) {
                // إذا لم يكن تطبيق Android، استخدم API المتصفح العادي
                resolve();
                return;
            }

            // عرض نافذة طلب الإذن للمستخدم
            const permissionPopup = document.getElementById('permission-popup');
            permissionPopup.style.display = 'block';

            document.getElementById('grant-permission-btn').onclick = function() {
                permissionPopup.style.display = 'none';
                resolve();
            };

            document.getElementById('deny-permission-btn').onclick = function() {
                permissionPopup.style.display = 'none';
                reject(new Error('تم رفض الإذن من قبل المستخدم'));
            };
        });
    }

    function locateUser() {
        const locateBtn = document.getElementById('locate-me-btn');
        
        if (watchId) {
            // إذا كان التتبع نشطاً، أوقفه
            navigator.geolocation.clearWatch(watchId);
            watchId = null;
            
            if (userLocationMarker) {
                map.removeLayer(userLocationMarker);
                userLocationMarker = null;
            }
            
            locateBtn.innerHTML = '<i class="fas fa-location-arrow"></i> موقعي الحالي';
            locateBtn.style.backgroundColor = '#ffc107';
            locateBtn.style.color = '#000';
            return;
        }
        
        if (!navigator.geolocation) {
            alert('متصفحك لا يدعم خدمة تحديد الموقع');
            return;
        }
        
        locateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري التتبع...';
        locateBtn.style.backgroundColor = '#007bff';
        locateBtn.style.color = '#fff';
        
        // إنشاء علامة للمستخدم
        const userIcon = L.divIcon({
            className: 'user-location-marker',
            iconSize: [20, 20]
        });
        
        // طلب إذن الوصول إلى الموقع
        requestLocationPermission()
            .then(() => {
                // في تطبيق Android، نحتاج إلى استخدام جافا سكريبت للاتصال بالكود الأصلي
                if (isAndroidApp && window.AndroidInterface) {
                    try {
                        window.AndroidInterface.requestLocationPermission();
                    } catch (e) {
                        console.error('Error calling Android interface:', e);
                    }
                }
                
                watchId = navigator.geolocation.watchPosition(
                    (position) => {
                        const { latitude, longitude } = position.coords;
                        
                        if (!userLocationMarker) {
                            userLocationMarker = L.marker([latitude, longitude], {
                                icon: userIcon,
                                zIndexOffset: 1000
                            }).addTo(map)
                            .bindPopup('<b>موقعك الحالي</b>');
                        } else {
                            userLocationMarker.setLatLng([latitude, longitude]);
                        }
                        
                        // تكبير الخريطة على الموقع الحالي
                        map.setView([latitude, longitude], 17);
                        
                        locateBtn.innerHTML = '<i class="fas fa-location-arrow"></i> إيقاف التتبع';
                    },
                    (error) => {
                        console.error('Error getting location:', error);
                        let errorMessage = 'حدث خطأ في الحصول على الموقع';
                        
                        switch(error.code) {
                            case error.PERMISSION_DENIED:
                                errorMessage = 'تم رفض إذن الوصول إلى الموقع';
                                break;
                            case error.POSITION_UNAVAILABLE:
                                errorMessage = 'معلومات الموقع غير متوفرة';
                                break;
                            case error.TIMEOUT:
                                errorMessage = 'انتهت مهلة طلب الموقع';
                                break;
                            case error.UNKNOWN_ERROR:
                                errorMessage = 'حدث خطأ غير معروف';
                                break;
                        }
                        
                        alert(errorMessage);
                        
                        locateBtn.innerHTML = '<i class="fas fa-location-arrow"></i> موقعي الحالي';
                        locateBtn.style.backgroundColor = '#ffc107';
                        locateBtn.style.color = '#000';
                        watchId = null;
                    },
                    {
                        enableHighAccuracy: true,
                        maximumAge: 10000,
                        timeout: 15000
                    }
                );
            })
            .catch(error => {
                console.error('Permission error:', error);
                alert('لا يمكن تحديد الموقع بدون إذن الوصول');
                
                locateBtn.innerHTML = '<i class="fas fa-location-arrow"></i> موقعي الحالي';
                locateBtn.style.backgroundColor = '#ffc107';
                locateBtn.style.color = '#000';
            });
    }

    document.addEventListener('DOMContentLoaded', () => {
        initMap();
        setInterval(updateDevices, 3000);

        const adminBtn = document.getElementById('admin-btn');
        const passcodePopup = document.getElementById('passcode-popup');
        const passcodeInput = document.getElementById('passcode-input');
        const passcodeSubmit = document.getElementById('passcode-submit');
        const passcodeError = document.getElementById('passcode-error');
        const closeControlBtn = document.getElementById('close-control');
        const showNamesBtn = document.getElementById('show-names-btn');
        const locateMeBtn = document.getElementById('locate-me-btn');

        adminBtn.addEventListener('click', () => {
            passcodePopup.style.display = 'block';
            passcodeInput.focus();
        });

        passcodeSubmit.addEventListener('click', () => {
            const code = passcodeInput.value.trim();
            if (code === '1234560') {
                document.getElementById('control-panel').style.display = 'block';
                passcodePopup.style.display = 'none';
                adminBtn.style.display = 'none';
                passcodeError.style.display = 'none';
                updateDevices();
            } else {
                passcodeError.style.display = 'block';
            }
        });

        passcodeInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                passcodeSubmit.click();
            }
        });

        closeControlBtn.addEventListener('click', () => {
            document.getElementById('control-panel').style.display = 'none';
            adminBtn.style.display = 'block';
        });

        showNamesBtn.addEventListener('click', () => {
            document.getElementById('device-names-panel').style.display = 'block';
            updateDevices();
        });

        locateMeBtn.addEventListener('click', locateUser);
    });

    // دالة يمكن استدعاؤها من تطبيق Android بعد منح الإذن
    function onLocationPermissionGranted() {
        console.log('Location permission granted by Android app');
        // يمكنك تنفيذ أي إجراء إضافي هنا إذا لزم الأمر
    }
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
        
        # الحصول على الوقت الحالي بتوقيت UTC وإضافة معلومات المنطقة الزمنية
        now_utc = datetime.utcnow()
        devices[device_id].update({
            'lat': float(lat),
            'lon': float(lon),
            'timestamp': data.get('timestamp'),
            'battery': data.get('batt'),
            'speed': data.get('speed'),
            'accuracy': data.get('accuracy'),
            'last_update': now_utc.isoformat() + 'Z'  # ISO format with Z for UTC
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

@app.route('/delete_device', methods=['POST'])
def delete_device():
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        if not device_id:
            return jsonify({'success': False, 'message': 'بيانات ناقصة'}), 400
        
        if device_id in devices:
            del devices[device_id]
            print(f"تم حذف الجهاز {device_id} بنجاح")
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'message': 'الجهاز غير موجود'}), 404
    except Exception as e:
        print(f"خطأ في حذف الجهاز: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ في الخادم'}), 500

@app.route('/get_devices', methods=['GET'])
def get_devices():
    return jsonify(devices)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)