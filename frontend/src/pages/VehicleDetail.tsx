import { useCallback, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchVehicle, fmtDate, type Vehicle } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import Spinner from "../components/Spinner";

export default function VehicleDetail() {
  const { vin } = useParams<{ vin: string }>();
  const fetcher = useCallback(() => fetchVehicle(vin!), [vin]);
  const { data: vehicle, loading, error } = useFetch<Vehicle>(fetcher, [vin]);
  const [activePhoto, setActivePhoto] = useState(0);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !vehicle) {
    return (
      <div className="space-y-4">
        <Link to="/inventory" className="btn-secondary text-sm inline-flex items-center gap-1">
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
          Back to Inventory
        </Link>
        <div className="rounded-lg bg-red-50 border border-red-200 p-6 text-red-700">
          <h3 className="font-semibold">Vehicle Not Found</h3>
          <p className="mt-1 text-sm">{error?.message || `No vehicle found with VIN: ${vin}`}</p>
        </div>
      </div>
    );
  }

  const title = [vehicle.year, vehicle.make, vehicle.model].filter(Boolean).join(" ");
  const photos = vehicle.photos || [];

  const specs = [
    { label: "VIN", value: vehicle.vin },
    { label: "Stock #", value: vehicle.stock_number },
    { label: "Year", value: vehicle.year },
    { label: "Make", value: vehicle.make },
    { label: "Model", value: vehicle.model },
    { label: "Trim", value: vehicle.trim },
    { label: "Price", value: vehicle.price ? `$${Number(vehicle.price).toLocaleString()}` : null },
    { label: "Mileage", value: vehicle.mileage ? `${vehicle.mileage.toLocaleString()} mi` : null },
    { label: "Exterior Color", value: vehicle.exterior_color },
    { label: "Interior Color", value: vehicle.interior_color },
    { label: "Body Style", value: vehicle.body_style },
    { label: "Drivetrain", value: vehicle.drivetrain },
    { label: "Engine", value: vehicle.engine },
    { label: "Transmission", value: vehicle.transmission },
  ].filter((s) => s.value);

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        to="/inventory"
        className="btn-secondary text-sm inline-flex items-center gap-1"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
        </svg>
        Back to Inventory
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Image Gallery */}
        <div className="space-y-3">
          {/* Main Image */}
          <div className="card overflow-hidden aspect-[4/3] bg-gray-100">
            {photos.length > 0 ? (
              <img
                src={photos[activePhoto]}
                alt={`${title} photo ${activePhoto + 1}`}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-gray-400">
                <svg className="h-20 w-20" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21Z" />
                </svg>
              </div>
            )}
          </div>

          {/* Thumbnail Strip */}
          {photos.length > 1 && (
            <div className="flex gap-2 overflow-x-auto pb-2">
              {photos.map((photo, idx) => (
                <button
                  key={idx}
                  onClick={() => setActivePhoto(idx)}
                  className={`flex-shrink-0 h-16 w-20 overflow-hidden rounded-lg border-2 transition-all ${
                    idx === activePhoto
                      ? "border-brand-600 ring-2 ring-brand-200"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <img
                    src={photo}
                    alt={`Thumbnail ${idx + 1}`}
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Vehicle Info */}
        <div className="space-y-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{title || "Unknown Vehicle"}</h1>
            {vehicle.trim && (
              <p className="mt-1 text-lg text-gray-500">{vehicle.trim}</p>
            )}
            {vehicle.price && (
              <p className="mt-2 text-3xl font-bold text-brand-600">
                ${Number(vehicle.price).toLocaleString()}
              </p>
            )}
          </div>

          {/* Status */}
          <div className="flex gap-2">
            {vehicle.is_active ? (
              <span className="badge bg-green-100 text-green-700 text-sm px-3 py-1">Active Listing</span>
            ) : (
              <span className="badge bg-gray-100 text-gray-500 text-sm px-3 py-1">Inactive</span>
            )}
            {vehicle.detail_url && (
              <a
                href={vehicle.detail_url}
                target="_blank"
                rel="noopener noreferrer"
                className="badge bg-blue-100 text-blue-700 text-sm px-3 py-1 hover:bg-blue-200 transition-colors"
              >
                View on Source
              </a>
            )}
          </div>

          {/* Specs Table */}
          <div className="card overflow-hidden">
            <div className="border-b border-gray-200 px-5 py-3 bg-gray-50">
              <h2 className="font-semibold text-gray-900">Vehicle Specifications</h2>
            </div>
            <div className="divide-y divide-gray-100">
              {specs.map(({ label, value }) => (
                <div key={label} className="flex justify-between px-5 py-3">
                  <span className="text-sm text-gray-500">{label}</span>
                  <span className="text-sm font-medium text-gray-900">{String(value)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Timestamps */}
          <div className="text-xs text-gray-400 space-y-1">
            <p>Added: {fmtDate(vehicle.created_at)}</p>
            {vehicle.updated_at && (
              <p>Last updated: {fmtDate(vehicle.updated_at)}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
