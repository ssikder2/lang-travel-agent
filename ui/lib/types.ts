export interface FlightCard {
  airline: string;
  airline_logo: string | null;
  departure: { code: string; time: string };
  arrival: { code: string; time: string };
  duration: string;
  stops: number;
  price: number;
  url: string;
}

export interface HotelCard {
  name: string;
  price_per_night: string;
  total_price?: string;
  rating?: number;
  reviews?: number;
  free_cancellation: boolean;
  amenities: string[];
  hotel_class?: string;
  link?: string;
  image?: string;
}

export type CardsData =
  | { kind: "flights"; label: string; cards: FlightCard[] }
  | { kind: "hotels"; label: string; cards: HotelCard[] };

export interface TripProfileSnapshot {
  destinations?: string;
  travel_dates?: string;
  num_travelers?: number;
  travel_style?: string;
  flight_departure?: string;
  flight_trip_type?: string;
  flight_outbound_ymd?: string;
  flight_return_ymd?: string;
  interests?: string;
  flights?: string;
  hotels?: string;
  transportation?: string;
  budget_estimate?: string;
  special_notes?: string;
}
