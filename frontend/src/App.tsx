import { Routes, Route } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { ProfileProvider } from "./context/ProfileContext";
import { HomePage } from "./pages/shop/HomePage";
import { SearchPage } from "./pages/shop/SearchPage";
import { ProductPage } from "./pages/shop/ProductPage";
import { ProfilePage } from "./pages/shop/ProfilePage";
import { RulesAdminPage } from "./pages/admin/RulesAdminPage";
import { LiveLogsPage } from "./pages/admin/LiveLogsPage";

function App() {
  return (
    <ProfileProvider>
      <NavBar />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/product/:id" element={<ProductPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/admin" element={<RulesAdminPage />} />
        <Route path="/admin/logs" element={<LiveLogsPage />} />
      </Routes>
    </ProfileProvider>
  );
}

export default App;
