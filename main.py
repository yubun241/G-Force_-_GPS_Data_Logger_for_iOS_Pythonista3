import motion
import scene
import ui
import location
import datetime
import csv
import math
import os

class GForceMeter(scene.Scene):
    def setup(self):
        # --- センサー開始 ---
        motion.start_updates()
        location.start_updates()
        
        self.max_g = 0.0
        self.peak_pos = scene.Point(0, 0)
        self.max_display_g = 2.5
        self.scale = (self.size.w / 2) / self.max_display_g
        
        # --- しきい値設定 ---
        self.threshold_g = 1.1
        
        # --- 記録用変数 ---
        self.is_recording = False
        self.log_file = None
        self.writer = None
        self.last_location = None
        self.last_time = None
        self.current_speed = 0.0
        
        # --- UIレイアウト ---
        sw, sh = self.size.w, self.size.h
        # RECボタン
        self.rec_button_rect = scene.Rect(sw/2 - 60, 50, 120, 50)
        # しきい値調整ボタン (左下)
        self.minus_button_rect = scene.Rect(30, 50, 60, 50)
        self.plus_button_rect = scene.Rect(100, 50, 60, 50)

    def stop(self):
        motion.stop_updates()
        location.stop_updates()
        if self.log_file:
            self.log_file.close()

    def calculate_speed(self, current_loc):
        if not self.last_location or not self.last_time:
            self.last_location = current_loc
            self.last_time = datetime.datetime.now()
            return 0.0
        
        now = datetime.datetime.now()
        dt = (now - self.last_time).total_seconds()
        if dt <= 0: return self.current_speed
        
        lat1, lon1 = math.radians(self.last_location['latitude']), math.radians(self.last_location['longitude'])
        lat2, lon2 = math.radians(current_loc['latitude']), math.radians(current_loc['longitude'])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = 6371000 * c
        
        speed = (distance / dt) * 3.6
        self.last_location = current_loc
        self.last_time = now
        return speed

    def draw(self):
        accel = motion.get_user_acceleration()
        loc = location.get_location()
        gx, gy, gz = accel if accel else (0, 0, 0)
        current_total_g = (gx**2 + gy**2 + gz**2)**0.5
        
        if self.is_recording and accel and loc:
            self.record_data(gx, gy, gz, current_total_g, loc)

        # アラート色判定
        scene.background(0.6, 0, 0) if current_total_g > self.threshold_g else scene.background(0, 0, 0)
        center = self.size / 2
        
        if current_total_g > self.max_g:
            self.max_g = current_total_g
            self.peak_pos = scene.Point(gx * self.scale, gz * self.scale)

        # --- 目盛りとガイド線 ---
        scene.no_fill()
        # 固定目盛り
        for g_step in [0.5, 1.0, 1.5, 2.0, 2.5]:
            r = g_step * self.scale * 2
            scene.stroke(0.4, 0.4, 0.4)
            scene.stroke_weight(1)
            scene.ellipse(center.x - g_step*self.scale, center.y - g_step*self.scale, r, r)
        
        # しきい値の円 (黄色)
        scene.stroke(1, 1, 0)
        scene.stroke_weight(2)
        tr = self.threshold_g * self.scale * 2
        scene.ellipse(center.x - self.threshold_g*self.scale, center.y - self.threshold_g*self.scale, tr, tr)

        # --- Gドット描画 ---
        scene.fill(1, 1, 1, 0.5) # ピーク
        scene.ellipse(center.x + self.peak_pos.x - 6, center.y + self.peak_pos.y - 6, 12, 12)
        scene.fill(1, 1, 1) if current_total_g > self.threshold_g else scene.fill(0, 1, 0)
        scene.ellipse(center.x + gx*self.scale - 15, center.y + gz*self.scale - 15, 30, 30)

        # --- 情報表示 ---
        scene.tint(1, 1, 1)
        scene.text(f'TOTAL G: {current_total_g:.2f}', x=center.x, y=center.y + 320, font_size=28)
        scene.text(f'MAX G: {self.max_g:.2f}', x=center.x, y=center.y - 320, font_size=32)
        scene.text(f'SPEED: {self.current_speed:.1f} km/h', x=center.x, y=center.y - 250, font_size=20)
        
        # --- UIボタン類 ---
        # RECボタン
        scene.fill(1, 0, 0) if not self.is_recording else scene.fill(0.5, 0.5, 0.5)
        scene.rect(*self.rec_button_rect)
        scene.tint(1, 1, 1)
        btn_label = 'START REC' if not self.is_recording else 'STOP REC'
        scene.text(btn_label, x=self.rec_button_rect.center().x, y=self.rec_button_rect.center().y, font_size=16)
        
        # しきい値調整ボタン
        scene.fill(0.2, 0.2, 0.2)
        scene.rect(*self.minus_button_rect)
        scene.rect(*self.plus_button_rect)
        scene.tint(1, 1, 1)
        scene.text('-', x=self.minus_button_rect.center().x, y=self.minus_button_rect.center().y, font_size=24)
        scene.text('+', x=self.plus_button_rect.center().x, y=self.plus_button_rect.center().y, font_size=24)
        scene.text(f'Alert: {self.threshold_g:.1f}G', x=80, y=120, font_size=14)

    def record_data(self, gx, gy, gz, total_g, loc):
        self.current_speed = self.calculate_speed(loc)
        now = datetime.datetime.now()
        row = [now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S.%f')[:12], gx, gy, gz, total_g, loc['latitude'], loc['longitude'], self.current_speed]
        self.writer.writerow(row)

    def touch_began(self, touch):
        if touch.location in self.rec_button_rect:
            if not self.is_recording: self.start_logging()
            else: self.stop_logging()
        elif touch.location in self.minus_button_rect:
            self.threshold_g = max(0.1, self.threshold_g - 0.1)
        elif touch.location in self.plus_button_rect:
            self.threshold_g = min(2.5, self.threshold_g + 0.1)
        else:
            self.max_g = 0
            self.peak_pos = scene.Point(0, 0)

    def start_logging(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(os.path.dirname(base_dir), 'data')
        if not os.path.exists(data_dir): os.makedirs(data_dir)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%m%d%H%M%S')
        file_path = os.path.join(data_dir, f"recordData_{timestamp}.csv")
        self.log_file = open(file_path, 'w', newline='')
        self.writer = csv.writer(self.log_file)
        self.writer.writerow(['Date', 'Time', 'G_X', 'G_Y', 'G_Z', 'G_Combined', 'Lat', 'Lon', 'Speed_kmh'])
        self.is_recording = True

    def stop_logging(self):
        self.is_recording = False
        if self.log_file:
            self.log_file.close()
            self.log_file = None

scene.run(GForceMeter(), orientation=scene.PORTRAIT)
