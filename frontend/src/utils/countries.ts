/**
 * Country and city options for relocation forms.
 * Extensible: add more countries/cities as needed.
 */

export interface CountryOption {
  code: string;
  name: string;
  cities: string[];
}

/** Countries and cities, alphabetically by country name, cities within each country alphabetically. */
export const COUNTRY_OPTIONS: CountryOption[] = [
  { code: 'AR', name: 'Argentina', cities: ['Buenos Aires', 'Córdoba', 'La Plata', 'Mar del Plata', 'Mendoza', 'Rosario', 'Salta', 'San Juan', 'San Miguel de Tucumán', 'Santa Fe'] },
  { code: 'AT', name: 'Austria', cities: ['Dornbirn', 'Graz', 'Innsbruck', 'Klagenfurt', 'Linz', 'Salzburg', 'St. Pölten', 'Vienna', 'Villach', 'Wels'] },
  { code: 'AU', name: 'Australia', cities: ['Adelaide', 'Brisbane', 'Canberra', 'Gold Coast', 'Melbourne', 'Newcastle', 'Perth', 'Sunshine Coast', 'Sydney', 'Wollongong'] },
  { code: 'BE', name: 'Belgium', cities: ['Aalst', 'Antwerp', 'Bruges', 'Brussels', 'Charleroi', 'Ghent', 'Leuven', 'Liège', 'Mons', 'Namur'] },
  { code: 'BR', name: 'Brazil', cities: ['Belo Horizonte', 'Brasília', 'Curitiba', 'Fortaleza', 'Manaus', 'Porto Alegre', 'Recife', 'Rio de Janeiro', 'Salvador', 'São Paulo'] },
  { code: 'CA', name: 'Canada', cities: ['Calgary', 'Edmonton', 'Hamilton', 'Kitchener', 'Montreal', 'Ottawa', 'Quebec City', 'Toronto', 'Vancouver', 'Winnipeg'] },
  { code: 'CH', name: 'Switzerland', cities: ['Basel', 'Bern', 'Biel', 'Geneva', 'Lausanne', 'Lucerne', 'Lugano', 'St. Gallen', 'Winterthur', 'Zurich'] },
  { code: 'CL', name: 'Chile', cities: ['Antofagasta', 'Arica', 'Concepción', 'Iquique', 'La Serena', 'Rancagua', 'Santiago', 'Talca', 'Temuco', 'Valparaíso'] },
  { code: 'CN', name: 'China', cities: ['Beijing', 'Chengdu', 'Guangzhou', 'Hangzhou', 'Nanjing', 'Shanghai', 'Shenzhen', 'Tianjin', 'Wuhan', 'Xi\'an'] },
  { code: 'CO', name: 'Colombia', cities: ['Barranquilla', 'Bogotá', 'Bucaramanga', 'Cali', 'Cartagena', 'Cúcuta', 'Ibagué', 'Medellín', 'Pereira', 'Santa Marta'] },
  { code: 'CZ', name: 'Czech Republic', cities: ['Brno', 'České Budějovice', 'Hradec Králové', 'Liberec', 'Olomouc', 'Ostrava', 'Pardubice', 'Pilsen', 'Prague', 'Ústí nad Labem'] },
  { code: 'DE', name: 'Germany', cities: ['Berlin', 'Bremen', 'Cologne', 'Dortmund', 'Dresden', 'Duisburg', 'Düsseldorf', 'Essen', 'Frankfurt', 'Hamburg', 'Hannover', 'Leipzig', 'Munich', 'Nuremberg', 'Stuttgart'] },
  { code: 'DK', name: 'Denmark', cities: ['Aalborg', 'Aarhus', 'Copenhagen', 'Esbjerg', 'Frederiksberg', 'Gentofte', 'Gladsaxe', 'Kolding', 'Odense', 'Randers'] },
  { code: 'ES', name: 'Spain', cities: ['Barcelona', 'Bilbao', 'Las Palmas', 'Madrid', 'Málaga', 'Murcia', 'Palma', 'Seville', 'Valencia', 'Zaragoza'] },
  { code: 'FI', name: 'Finland', cities: ['Espoo', 'Helsinki', 'Jyväskylä', 'Kuopio', 'Lahti', 'Oulu', 'Pori', 'Tampere', 'Turku', 'Vantaa'] },
  { code: 'FR', name: 'France', cities: ['Bordeaux', 'Grenoble', 'Lille', 'Lyon', 'Marseille', 'Montpellier', 'Nantes', 'Nice', 'Paris', 'Reims', 'Rennes', 'Saint-Étienne', 'Strasbourg', 'Toulon', 'Toulouse'] },
  { code: 'GR', name: 'Greece', cities: ['Athens', 'Chalcis', 'Chania', 'Heraklion', 'Ioannina', 'Larissa', 'Patras', 'Rhodes', 'Thessaloniki', 'Volos'] },
  { code: 'HK', name: 'Hong Kong', cities: ['Hong Kong', 'Kowloon', 'New Territories'] },
  { code: 'HU', name: 'Hungary', cities: ['Budapest', 'Debrecen', 'Győr', 'Kecskemét', 'Miskolc', 'Nyíregyháza', 'Pécs', 'Szeged', 'Székesfehérvár', 'Szombathely'] },
  { code: 'IE', name: 'Ireland', cities: ['Bray', 'Cork', 'Drogheda', 'Dublin', 'Dundalk', 'Galway', 'Limerick', 'Navan', 'Swords', 'Waterford'] },
  { code: 'IL', name: 'Israel', cities: ['Ashdod', 'Bnei Brak', 'Haifa', 'Holon', 'Jerusalem', 'Netanya', 'Petah Tikva', 'Ramat Gan', 'Rishon LeZion', 'Tel Aviv'] },
  { code: 'IN', name: 'India', cities: ['Ahmedabad', 'Bangalore', 'Chennai', 'Delhi', 'Hyderabad', 'Jaipur', 'Kolkata', 'Mumbai', 'Pune', 'Surat'] },
  { code: 'IT', name: 'Italy', cities: ['Bologna', 'Florence', 'Genoa', 'Milan', 'Naples', 'Palermo', 'Rome', 'Turin', 'Venice', 'Verona'] },
  { code: 'JP', name: 'Japan', cities: ['Fukuoka', 'Kawasaki', 'Kobe', 'Kyoto', 'Nagoya', 'Osaka', 'Saitama', 'Sapporo', 'Tokyo', 'Yokohama'] },
  { code: 'KR', name: 'South Korea', cities: ['Busan', 'Changwon', 'Daegu', 'Daejeon', 'Gwangju', 'Incheon', 'Seongnam', 'Seoul', 'Suwon', 'Ulsan'] },
  { code: 'MX', name: 'Mexico', cities: ['Cancún', 'Guadalajara', 'Juárez', 'León', 'Mérida', 'Mexico City', 'Monterrey', 'Puebla', 'Tijuana', 'Zapopan'] },
  { code: 'NL', name: 'Netherlands', cities: ['Almere', 'Amsterdam', 'Breda', 'Eindhoven', 'Groningen', 'Nijmegen', 'Rotterdam', 'The Hague', 'Tilburg', 'Utrecht'] },
  { code: 'NO', name: 'Norway', cities: ['Bergen', 'Drammen', 'Fredrikstad', 'Kristiansand', 'Oslo', 'Sandefjord', 'Sarpsborg', 'Stavanger', 'Tromsø', 'Trondheim'] },
  { code: 'NZ', name: 'New Zealand', cities: ['Auckland', 'Christchurch', 'Dunedin', 'Hamilton', 'Napier', 'Nelson', 'Palmerston North', 'Rotorua', 'Tauranga', 'Wellington'] },
  { code: 'PL', name: 'Poland', cities: ['Bydgoszcz', 'Gdańsk', 'Katowice', 'Kraków', 'Lublin', 'Łódź', 'Poznań', 'Szczecin', 'Warsaw', 'Wrocław'] },
  { code: 'PT', name: 'Portugal', cities: ['Almada', 'Amadora', 'Aveiro', 'Braga', 'Coimbra', 'Faro', 'Funchal', 'Lisbon', 'Porto', 'Setúbal'] },
  { code: 'RO', name: 'Romania', cities: ['Brașov', 'Bucharest', 'Cluj-Napoca', 'Constanța', 'Craiova', 'Galați', 'Iași', 'Oradea', 'Ploiești', 'Timișoara'] },
  { code: 'RU', name: 'Russia', cities: ['Chelyabinsk', 'Kazan', 'Moscow', 'Nizhny Novgorod', 'Novosibirsk', 'Rostov-on-Don', 'Saint Petersburg', 'Samara', 'Ufa', 'Yekaterinburg'] },
  { code: 'SE', name: 'Sweden', cities: ['Gothenburg', 'Helsingborg', 'Jönköping', 'Linköping', 'Malmö', 'Norrköping', 'Stockholm', 'Uppsala', 'Västerås', 'Örebro'] },
  { code: 'SG', name: 'Singapore', cities: ['Singapore'] },
  { code: 'TR', name: 'Turkey', cities: ['Adana', 'Ankara', 'Antalya', 'Bursa', 'Diyarbakır', 'Gaziantep', 'Istanbul', 'Izmir', 'Konya', 'Mersin'] },
  { code: 'UK', name: 'United Kingdom', cities: ['Belfast', 'Birmingham', 'Bristol', 'Cardiff', 'Edinburgh', 'Glasgow', 'Leeds', 'Liverpool', 'London', 'Manchester', 'Newcastle', 'Nottingham', 'Sheffield', 'Southampton'] },
  { code: 'AE', name: 'United Arab Emirates', cities: ['Abu Dhabi', 'Ajman', 'Dubai', 'Fujairah', 'Ras Al Khaimah', 'Sharjah', 'Umm Al Quwain'] },
  { code: 'US', name: 'United States', cities: ['Austin', 'Boston', 'Chicago', 'Columbus', 'Dallas', 'Denver', 'Houston', 'Jacksonville', 'Los Angeles', 'New York', 'Philadelphia', 'Phoenix', 'San Antonio', 'San Diego', 'San Francisco', 'San Jose', 'Seattle', 'Washington'] },
  { code: 'ZA', name: 'South Africa', cities: ['Bloemfontein', 'Cape Town', 'Durban', 'East London', 'Johannesburg', 'Pietermaritzburg', 'Port Elizabeth', 'Pretoria'] },
];

/** Get cities for a country by name */
export function getCitiesForCountry(countryName: string): string[] {
  const country = COUNTRY_OPTIONS.find((c) => c.name === countryName);
  return country?.cities ?? [];
}

/** Check if a city is in the predefined list for a country */
export function isCityInList(countryName: string, city: string): boolean {
  const cities = getCitiesForCountry(countryName);
  return cities.includes(city);
}
