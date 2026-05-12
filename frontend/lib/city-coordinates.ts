import type { Coordinates } from "@/types/trip";

const cityCoordinates: Record<string, Coordinates> = {
  北京: { lat: 39.9042, lng: 116.4074 },
  上海: { lat: 31.2304, lng: 121.4737 },
  广州: { lat: 23.1291, lng: 113.2644 },
  深圳: { lat: 22.5431, lng: 114.0579 },
  杭州: { lat: 30.2741, lng: 120.1551 },
  南京: { lat: 32.0603, lng: 118.7969 },
  苏州: { lat: 31.2989, lng: 120.5853 },
  成都: { lat: 30.5728, lng: 104.0668 },
  重庆: { lat: 29.563, lng: 106.5516 },
  武汉: { lat: 30.5928, lng: 114.3055 },
  西安: { lat: 34.3416, lng: 108.9398 },
  天津: { lat: 39.3434, lng: 117.3616 },
  长沙: { lat: 28.2282, lng: 112.9388 },
  郑州: { lat: 34.7466, lng: 113.6254 },
  青岛: { lat: 36.0671, lng: 120.3826 },
  厦门: { lat: 24.4798, lng: 118.0894 },
  福州: { lat: 26.0745, lng: 119.2965 },
  昆明: { lat: 25.0389, lng: 102.7183 },
  大理: { lat: 25.6065, lng: 100.2676 },
  三亚: { lat: 18.2528, lng: 109.5119 },
  海口: { lat: 20.0442, lng: 110.1999 },
  哈尔滨: { lat: 45.8038, lng: 126.5349 },
  沈阳: { lat: 41.8057, lng: 123.4315 },
  长春: { lat: 43.8171, lng: 125.3235 },
  济南: { lat: 36.6512, lng: 117.1201 },
  合肥: { lat: 31.8206, lng: 117.2272 },
  南昌: { lat: 28.682, lng: 115.8579 },
  南宁: { lat: 22.817, lng: 108.3669 },
  贵阳: { lat: 26.647, lng: 106.6302 },
  兰州: { lat: 36.0611, lng: 103.8343 },
  太原: { lat: 37.8706, lng: 112.5489 },
  呼和浩特: { lat: 40.8426, lng: 111.7492 },
  乌鲁木齐: { lat: 43.8256, lng: 87.6168 },
};

export function getCityCoordinates(city?: string | null): Coordinates | null {
  if (!city) return null;

  let normalized = city.trim();
  for (const suffix of ["市", "省", "自治区", "特别行政区"]) {
    if (normalized.endsWith(suffix)) {
      normalized = normalized.slice(0, -suffix.length);
      break;
    }
  }

  return cityCoordinates[normalized] ?? null;
}
