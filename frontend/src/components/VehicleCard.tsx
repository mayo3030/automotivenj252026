import { Link } from "react-router-dom";
import type { Vehicle } from "../api/client";

interface VehicleCardProps {
  vehicle: Vehicle;
  view?: "grid" | "table";
}

export default function VehicleCard({ vehicle, view = "grid" }: VehicleCardProps) {
  const thumbnail =
    vehicle.photos && vehicle.photos.length > 0
      ? vehicle.photos[0]
      : null;

  const title = [vehicle.year, vehicle.make, vehicle.model].filter(Boolean).join(" ");
  const price = vehicle.price
    ? `$${Number(vehicle.price).toLocaleString()}`
    : "Call for price";
  const mileage = vehicle.mileage
    ? `${vehicle.mileage.toLocaleString()} mi`
    : "N/A";

  if (view === "table") {
    return (
      <tr className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
        <td className="py-3 px-4">
          <Link to={`/inventory/${vehicle.vin}`} className="flex items-center gap-3">
            <div className="h-12 w-16 flex-shrink-0 overflow-hidden rounded-md bg-gray-100">
              {thumbnail ? (
                <img src={thumbnail} alt={title} className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-gray-400 text-xs">
                  No img
                </div>
              )}
            </div>
            <span className="font-medium text-brand-600 hover:underline">{title || "Unknown"}</span>
          </Link>
        </td>
        <td className="py-3 px-4 text-sm text-gray-500 font-mono">{vehicle.vin}</td>
        <td className="py-3 px-4 text-sm font-semibold">{price}</td>
        <td className="py-3 px-4 text-sm text-gray-500">{mileage}</td>
        <td className="py-3 px-4 text-sm text-gray-500">{vehicle.exterior_color || "—"}</td>
        <td className="py-3 px-4">
          {vehicle.is_active ? (
            <span className="badge bg-green-100 text-green-700">Active</span>
          ) : (
            <span className="badge bg-gray-100 text-gray-500">Inactive</span>
          )}
        </td>
      </tr>
    );
  }

  return (
    <Link
      to={`/inventory/${vehicle.vin}`}
      className="card group overflow-hidden transition-shadow hover:shadow-md"
    >
      <div className="aspect-[4/3] overflow-hidden bg-gray-100">
        {thumbnail ? (
          <img
            src={thumbnail}
            alt={title}
            className="h-full w-full object-cover transition-transform group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-gray-400">
            <svg className="h-12 w-12" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21Z" />
            </svg>
          </div>
        )}
      </div>
      <div className="p-4">
        <h3 className="font-semibold text-gray-900 group-hover:text-brand-600 transition-colors">
          {title || "Unknown Vehicle"}
        </h3>
        {vehicle.trim && (
          <p className="mt-0.5 text-xs text-gray-500">{vehicle.trim}</p>
        )}
        <div className="mt-2 flex items-center justify-between">
          <span className="text-lg font-bold text-brand-600">{price}</span>
          <span className="text-sm text-gray-500">{mileage}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {vehicle.exterior_color && (
            <span className="badge bg-gray-100 text-gray-600">{vehicle.exterior_color}</span>
          )}
          {vehicle.body_style && (
            <span className="badge bg-gray-100 text-gray-600">{vehicle.body_style}</span>
          )}
        </div>
        <p className="mt-2 text-xs text-gray-400 font-mono">{vehicle.vin}</p>
      </div>
    </Link>
  );
}
