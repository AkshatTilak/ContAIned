import React, { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useStore } from "../../store/useStore";
import { Loader2 } from "lucide-react";

export const AuthCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const setToken = useStore((state) => state.setToken);
  const checkAuth = useStore((state) => state.checkAuth);

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      setToken(token);
      checkAuth().then(() => {
        navigate("/", { replace: true });
      });
    } else {
      navigate("/login?error=missing_token", { replace: true });
    }
  }, [searchParams, setToken, checkAuth, navigate]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-950 text-slate-200">
      <Loader2 className="w-10 h-10 animate-spin text-indigo-500 mb-4" />
      <h2 className="text-lg font-medium text-slate-300">
        Authenticating & Initializing Session...
      </h2>
    </div>
  );
};
