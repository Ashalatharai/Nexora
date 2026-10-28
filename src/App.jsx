import React from "react";
import {
  ArrowDownLeft, ArrowLeft, ArrowRight, ArrowUpRight, Bell, Boxes,
  CalendarDays, Check, CheckCheck, ChevronDown, ChevronLeft, ChevronRight,
  CircleHelp, Clock3, CreditCard, Download, Ellipsis, Eye, EyeOff, FileBarChart2,
  Filter, Home, IndianRupee, LayoutDashboard, ListFilter, LogOut, Menu,
  MessageCircle, Mic, Minus, MoreHorizontal, Package, Plus, Search, Send,
  Settings, ShieldCheck, ShoppingBag, Sparkles, TrendingDown, TrendingUp,
  UserRound, Users, Wallet, X, AlertTriangle,
} from "lucide-react";
import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";

const StoreContext = createContext(null);
const STORAGE_KEY = "kirana-ledger-state-v1";

const seedState = {
  shop: { name: "Sharma General Store", owner: "Ramesh Sharma", phone: "+91 98765 43210", city: "Pune", address: "42, Laxmi Road, Pune" },
  products: [
    { id: "p1", name: "Amul Taaza Milk", category: "Dairy", price: 28, stock: 18, minStock: 20, unit: "packet", sku: "DAI-001" },
    { id: "p2", name: "Maggi 2-Minute Noodles", category: "Snacks", price: 14, stock: 42, minStock: 15, unit: "packet", sku: "SNK-014" },
    { id: "p3", name: "Tata Salt", category: "Essentials", price: 24, stock: 8, minStock: 12, unit: "packet", sku: "ESS-004" },
    { id: "p4", name: "Fortune Sunflower Oil", category: "Grocery", price: 145, stock: 26, minStock: 10, unit: "litre", sku: "GRC-008" },
    { id: "p5", name: "Aashirvaad Atta", category: "Grocery", price: 255, stock: 14, minStock: 8, unit: "kg", sku: "GRC-011" },
    { id: "p6", name: "Parle-G Biscuits", category: "Snacks", price: 10, stock: 64, minStock: 20, unit: "packet", sku: "SNK-002" },
    { id: "p7", name: "India Gate Basmati Rice", category: "Grocery", price: 120, stock: 6, minStock: 10, unit: "kg", sku: "GRC-016" },
    { id: "p8", name: "Surf Excel Easy Wash", category: "Household", price: 38, stock: 31, minStock: 10, unit: "packet", sku: "HOU-003" },
    { id: "p9", name: "Amul Butter", category: "Dairy", price: 58, stock: 12, minStock: 8, unit: "pack", sku: "DAI-009" },
    { id: "p10", name: "Good Day Cookies", category: "Snacks", price: 20, stock: 27, minStock: 12, unit: "packet", sku: "SNK-006" },
  ],
  customers: [
    { id: "c1", name: "Ramesh Patil", phone: "+91 98220 11234", due: 1250, lastActive: "Today", initials: "RP", color: "lavender" },
    { id: "c2", name: "Sunita Deshmukh", phone: "+91 97654 22411", due: 840, lastActive: "Today", initials: "SD", color: "peach" },
    { id: "c3", name: "Amit Kulkarni", phone: "+91 98900 55123", due: 560, lastActive: "Yesterday", initials: "AK", color: "blue" },
    { id: "c4", name: "Meena Joshi", phone: "+91 98230 99887", due: 2100, lastActive: "Yesterday", initials: "MJ", color: "mint" },
    { id: "c5", name: "Vikram More", phone: "+91 94220 77331", due: 350, lastActive: "2 days ago", initials: "VM", color: "rose" },
    { id: "c6", name: "Kavita Shah", phone: "+91 98901 34567", due: 0, lastActive: "Today", initials: "KS", color: "sand" },
  ],
  transactions: [
    { id: "t1", customerId: "c1", title: "Daily groceries", detail: "Ramesh Patil · 3 items", amount: 285, type: "credit", time: "10:42 AM", date: "Today" },
    { id: "t2", customerId: "", title: "UPI payment", detail: "Walk-in customer", amount: 620, type: "sale", time: "10:18 AM", date: "Today" },
    { id: "t3", customerId: "c2", title: "Credit payment received", detail: "Sunita Deshmukh · UPI", amount: 500, type: "payment", time: "9:56 AM", date: "Today" },
    { id: "t4", customerId: "", title: "Milk & essentials", detail: "Cash · 4 items", amount: 182, type: "sale", time: "9:32 AM", date: "Today" },
    { id: "t5", customerId: "c4", title: "Monthly groceries", detail: "Meena Joshi · 6 items", amount: 740, type: "credit", time: "Yesterday", date: "Yesterday" },
    { id: "t6", customerId: "", title: "Cash sale", detail: "Walk-in customer", amount: 450, type: "sale", time: "Yesterday", date: "Yesterday" },
  ],
  suppliers: [
    { id: "s1", name: "Shree Dairy Suppliers", category: "Dairy & milk", initials: "SD", color: "mint", delivery: "Same-day delivery", products: 4, minimum: 500 },
    { id: "s2", name: "Maharashtra Grocery Co.", category: "Grocery & staples", initials: "MG", color: "sand", delivery: "Next-day delivery", products: 12, minimum: 1000 },
    { id: "s3", name: "Pune General Distributors", category: "Snacks & household", initials: "PG", color: "lavender", delivery: "Next-day delivery", products: 8, minimum: 750 },
  ],
  todaySales: 4850,
  messages: [],
  onboardingComplete: false,
};


const API_BASE = "/api";

function getCategory(name) {
  const n = (name || "").toLowerCase();
  if (n.includes("milk") || n.includes("butter") || n.includes("curd") || n.includes("paneer")) return "Dairy";
  if (n.includes("maggi") || n.includes("biscuit") || n.includes("cookie") || n.includes("chips")) return "Snacks";
  if (n.includes("rice") || n.includes("oil") || n.includes("atta") || n.includes("dal") || n.includes("sugar")) return "Grocery";
  if (n.includes("soap") || n.includes("detergent") || n.includes("surf")) return "Household";
  if (n.includes("salt") || n.includes("tea")) return "Essentials";
  return "Grocery";
}

function mapBackendInventory(items) {
  if (!items || !items.length) return [];
  return items.map((item) => ({
    id: String(item.id),
    name: item.name.charAt(0).toUpperCase() + item.name.slice(1),
    category: getCategory(item.name),
    price: item.price,
    stock: item.quantity,
    minStock: item.min_threshold,
    unit: item.unit || "unit",
    sku: `SKU-${String(item.id).padStart(3, "0")}`,
    isLowStock: item.is_low_stock,
    isOutOfStock: item.is_out_of_stock,
  }));
}

function mapBackendCustomers(customers) {
  if (!customers || !customers.length) return [];
  const colors = ["mint", "lavender", "peach", "blue", "rose", "sand"];
  return customers.map((c, i) => ({
    id: String(c.id),
    name: c.name,
    phone: c.phone || "+91 98765 00000",
    due: c.outstanding_balance,
    lastActive: "Today",
    initials: c.name.slice(0, 2).toUpperCase(),
    color: colors[i % colors.length],
  }));
}

function readStoredState() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? { ...seedState, ...JSON.parse(stored) } : seedState;
  } catch {
    return seedState;
  }
}

function StoreProvider({ children }) {
  const [data, setData] = useState(readStoredState);
  const [backendConnected, setBackendConnected] = useState(false);

  const refreshBackend = async () => {
    try {
      const [invRes, custRes, sumRes] = await Promise.all([
        fetch(`${API_BASE}/inventory`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API_BASE}/credit/customers`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API_BASE}/summary/daily`).then((r) => (r.ok ? r.json() : null)),
      ]);

      setData((current) => {
        const next = { ...current };
        if (invRes && invRes.length > 0) {
          next.products = mapBackendInventory(invRes);
        }
        if (custRes && custRes.length > 0) {
          next.customers = mapBackendCustomers(custRes);
        }
        if (sumRes) {
          next.todaySales = sumRes.gross_sales_value_inr ?? sumRes.total_sales_amount ?? current.todaySales;
        }
        return next;
      });
      setBackendConnected(true);
    } catch (err) {
      console.warn("Could not reach Kirana backend, using local state:", err);
    }
  };

  useEffect(() => {
    refreshBackend();
  }, []);

  useEffect(() => localStorage.setItem(STORAGE_KEY, JSON.stringify(data)), [data]);
  const updateProduct = (id, updater) => setData((current) => ({ ...current, products: current.products.map((item) => item.id === id ? updater(item) : item) }));
  const addTransaction = (transaction) => setData((current) => ({
    ...current,
    transactions: [{ ...transaction, id: `t${Date.now()}`, time: "Just now", date: "Today" }, ...current.transactions],
    todaySales: transaction.type === "sale" ? current.todaySales + transaction.amount : current.todaySales,
  }));
  const value = { data, setData, updateProduct, addTransaction, refreshBackend, backendConnected };
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

const useStore = () => useContext(StoreContext);
const money = (value) => `₹${Number(value || 0).toLocaleString("en-IN")}`;

const navItems = [
  { to: "/dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { to: "/assistant", label: "Assistant", Icon: MessageCircle },
  { to: "/inventory", label: "Inventory", Icon: Boxes },
  { to: "/customers", label: "Customers", Icon: Users },
  { to: "/udhaar", label: "Udhaar", Icon: Wallet },
  { to: "/transactions", label: "Transactions", Icon: ArrowDownLeft },
  { to: "/reports", label: "Reports", Icon: FileBarChart2 },
  { to: "/low-stock", label: "Low stock", Icon: AlertTriangle },
];

const pageNames = {
  "/dashboard": "Dashboard", "/assistant": "Assistant", "/inventory": "Inventory",
  "/customers": "Customers", "/udhaar": "Udhaar", "/transactions": "Transactions",
  "/reports": "Reports", "/low-stock": "Low stock", "/settings": "Settings",
};

function Brand({ compact = false }) {
  return <Link className={`brand ${compact ? "brand-compact" : ""}`} to="/dashboard">
    <span className="brand-mark"><ShoppingBag size={19} strokeWidth={2.2} /><MessageCircle className="brand-chat" size={11} /></span>
    {!compact && <span className="brand-wordmark">kirana<span>ledger</span></span>}
  </Link>;
}

function Sidebar() {
  const location = useLocation();
  return <aside className="sidebar">
    <Brand />
    <div className="shop-switcher"><div className="shop-avatar">SG</div><div className="shop-switch-copy"><strong>Sharma General Store</strong><span>Free plan</span></div><ChevronDown size={15} /></div>
    <div className="nav-caption">WORKSPACE</div>
    <nav className="side-nav">
      {navItems.map(({ to, label, Icon }) => <NavLink key={to} to={to} className={({ isActive }) => `nav-link ${isActive && (to === "/dashboard" ? location.pathname === "/dashboard" : true) ? "active" : ""}`}>
        <Icon size={18} strokeWidth={1.8} /><span>{label}</span>{label === "Low stock" && <span className="nav-count">7</span>}
      </NavLink>)}
    </nav>
    <div className="sidebar-bottom">
      <NavLink to="/settings" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}><Settings size={18} strokeWidth={1.8} /><span>Settings</span></NavLink>
      <div className="help-card"><div className="help-icon"><CircleHelp size={17} /></div><div><strong>Need a hand?</strong><span>We're here to help</span></div><ArrowRight size={15} /></div>
      <button className="profile-card" onClick={() => window.location.assign("/settings")}><div className="profile-avatar">RS</div><div className="profile-copy"><strong>Ramesh Sharma</strong><span>Shop owner</span></div><MoreHorizontal size={17} /></button>
    </div>
  </aside>;
}

function Header({ title }) {
  const [showNotifications, setShowNotifications] = useState(false);
  const [search, setSearch] = useState("");
  const navigate = useNavigate();
  return <header className="topbar">
    <div className="mobile-brand"><Brand compact /><span>{title}</span></div>
    <div className="header-title">{title}</div>
    <div className="header-actions">
      <label className="global-search"><Search size={16} /><input placeholder="Search anything..." value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => event.key === "Enter" && navigate(`/inventory?search=${encodeURIComponent(search)}`)} /><kbd>⌘ K</kbd></label>
      <div className="notification-wrap"><button className="icon-button notification-button" aria-label="Notifications" onClick={() => setShowNotifications(!showNotifications)}><Bell size={18} /><i /></button>
        {showNotifications && <div className="notification-popover"><strong>Notifications</strong><div className="notification-item"><span className="notification-dot amber-dot" /><span><b>7 products are running low</b><small>Check your stock before it runs out.</small></span></div><div className="notification-item"><span className="notification-dot green-dot" /><span><b>Sales are looking good</b><small>You've made ₹4,850 today so far.</small></span></div></div>}
      </div>
      <button className="header-profile" onClick={() => navigate("/settings")}><span className="profile-avatar">RS</span><ChevronDown size={14} /></button>
    </div>
  </header>;
}

function AppShell() {
  const location = useLocation();
  const title = pageNames[location.pathname] || (location.pathname.startsWith("/inventory/") ? "Product details" : location.pathname.startsWith("/customers/") ? "Customer details" : "Kirana Ledger");
  return <div className="app-shell"><Sidebar /><div className="main-column"><Header title={title} /><main className="page-main"><Routes>
    <Route path="/dashboard" element={<Dashboard />} />
    <Route path="/assistant" element={<Assistant />} />
    <Route path="/inventory" element={<Inventory />} />
    <Route path="/inventory/:id" element={<ProductDetail />} />
    <Route path="/customers" element={<Customers />} />
    <Route path="/customers/:id" element={<CustomerDetail />} />
    <Route path="/udhaar" element={<Udhaar />} />
    <Route path="/transactions" element={<Transactions />} />
    <Route path="/reports" element={<Reports />} />
    <Route path="/low-stock" element={<LowStock />} />
    <Route path="/settings" element={<SettingsPage />} />
    <Route path="*" element={<Navigate to="/dashboard" replace />} />
  </Routes></main></div><MobileNav /></div>;
}

function MobileNav() {
  const items = navItems.slice(0, 5);
  return <nav className="mobile-nav">{items.map(({ to, label, Icon }) => <NavLink key={to} to={to} className={({ isActive }) => `mobile-nav-link ${isActive ? "active" : ""}`}><Icon size={19} /><span>{label === "Assistant" ? "Ask" : label === "Inventory" ? "Stock" : label}</span></NavLink>)}</nav>;
}

function PageIntro({ eyebrow, title, description, action }) {
  return <div className="page-intro"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{description && <p>{description}</p>}</div>{action && <div className="intro-action">{action}</div>}</div>;
}

function Button({ children, variant = "primary", icon: Icon, onClick, className = "", type = "button" }) {
  return <button type={type} onClick={onClick} className={`button button-${variant} ${className}`}>{Icon && <Icon size={16} />}{children}</button>;
}

function StatCard({ label, value, note, icon: Icon, tone, trend }) {
  return <div className="stat-card"><div className="stat-top"><span className="stat-label">{label}</span><span className={`stat-icon ${tone}`}><Icon size={18} /></span></div><div className="stat-value">{value}</div><div className="stat-note">{trend && <span className="trend-positive"><TrendingUp size={13} />{trend}</span>}{note}</div></div>;
}

function Dashboard() {
  const { data } = useStore();
  const navigate = useNavigate();
  const [reorderedSuppliers, setReorderedSuppliers] = useState([]);
  const lowProducts = data.products.filter((item) => item.stock <= item.minStock);
  const totalDue = data.customers.reduce((sum, item) => sum + item.due, 0);
  return <div className="dashboard-page">
    <div className="welcome-row"><div><div className="eyebrow">TUESDAY, 28 OCTOBER 2026</div><h1>Good morning, Ramesh <span className="wave">👋</span></h1><p>Here's what's happening in your shop today.</p></div><Button icon={MessageCircle} onClick={() => navigate("/assistant")}>Open Assistant</Button></div>
    <div className="stat-grid">
      <StatCard label="Today's sales" value={money(data.todaySales)} note="vs. ₹4,120 yesterday" trend="+17.7%" icon={IndianRupee} tone="green" />
      <StatCard label="Items in stock" value={data.products.reduce((sum, item) => sum + item.stock, 0).toLocaleString("en-IN")} note={`${data.products.length} products in your catalogue`} icon={Package} tone="blue" />
      <StatCard label="Udhaar to collect" value={money(totalDue)} note={`From ${data.customers.filter((c) => c.due > 0).length} customers`} icon={Wallet} tone="amber" />
      <StatCard label="Need restocking" value={`${lowProducts.length} items`} note="A few products are running low" icon={AlertTriangle} tone="rose" />
    </div>
    <div className="dashboard-grid">
      <section className="panel sales-panel"><div className="panel-heading"><div><h2>Sales overview</h2><p>Your shop is having a good week</p></div><button className="select-button">This week <ChevronDown size={14} /></button></div><SalesChart /></section>
      <section className="panel assistant-promo"><div className="assistant-promo-head"><div className="assistant-spark"><Sparkles size={18} /></div><span className="live-pill"><i /> READY TO HELP</span></div><h2>Your shop,<br />just a message away.</h2><p>Tell your assistant what happened. It’ll take care of your stock, sales and Udhaar.</p><div className="prompt-suggestion">“Sold 5 Maggi and 2 milk”<ArrowRight size={14} /></div><Button variant="light" icon={MessageCircle} onClick={() => navigate("/assistant")}>Talk to your assistant</Button></section>
    </div>
    <div className="dashboard-bottom-grid">
      <section className="panel"><div className="panel-heading"><div><h2>Recent activity</h2><p>The latest from your shop</p></div><Link className="text-link" to="/transactions">See all <ArrowRight size={14} /></Link></div><TransactionList transactions={data.transactions.slice(0, 4)} /></section>
      <section className="panel stock-panel"><div className="panel-heading"><div><h2>Stock to watch</h2><p>Items that may need a reorder</p></div><Link className="text-link" to="/low-stock">View all <ArrowRight size={14} /></Link></div>
        <div className="stock-watch-list">{lowProducts.slice(0, 4).map((product) => <Link to={`/inventory/${product.id}`} className="stock-watch-item" key={product.id}><ProductThumb product={product} /><span className="stock-watch-name"><strong>{product.name}</strong><small>{product.category}</small></span><span className="stock-level"><b>{product.stock}</b><small>{product.unit}s left</small></span></Link>)}</div>
      </section>
    </div>
    <section className="panel supplier-panel"><div className="panel-heading"><div><h2>Suppliers & reordering</h2><p>Keep your shelves stocked with the people who know your shop.</p></div><button className="select-button" onClick={() => navigate("/inventory")}><Package size={14} /> View low stock</button></div><div className="supplier-list">{data.suppliers.map((supplier) => <div className="supplier-row" key={supplier.id}><span className={`customer-avatar avatar-${supplier.color}`}>{supplier.initials}</span><span className="supplier-copy"><strong>{supplier.name}</strong><small>{supplier.category} · {supplier.delivery}</small></span><span className="supplier-products">{supplier.products} products</span><button className={`button ${reorderedSuppliers.includes(supplier.id) ? "button-secondary reorder-done" : "button-secondary"}`} onClick={() => setReorderedSuppliers((current) => current.includes(supplier.id) ? current : [...current, supplier.id])}>{reorderedSuppliers.includes(supplier.id) ? <><Check size={14} /> Requested</> : <><ArrowRight size={14} /> Reorder</>}</button></div>)}</div></section>
  </div>;
}

function SalesChart() {
  const heights = [42, 59, 48, 73, 62, 88, 67, 55, 76, 63, 92, 72, 81, 60, 75, 96, 65, 82, 70, 87, 67, 79, 58, 91, 74, 84, 69, 98];
  return <div className="chart-area"><div className="chart-y-labels"><span>₹6k</span><span>₹4k</span><span>₹2k</span><span>₹0</span></div><div className="chart-content"><div className="chart-gridlines"><i /><i /><i /><i /></div><div className="chart-bars">{heights.map((height, index) => <div key={index} className={`chart-bar ${index === 25 ? "chart-bar-highlight" : ""}`} style={{ height: `${height}%` }} title={`₹${(height * 55).toLocaleString("en-IN")}`} />)}</div><div className="chart-x-labels"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span></div></div></div>;
}

function ProductThumb({ product, large = false }) {
  const symbols = { Dairy: "🥛", Snacks: "🍪", Essentials: "🧂", Grocery: "🛍️", Household: "🧼" };
  return <span className={`product-thumb ${large ? "product-thumb-large" : ""} tone-${product.category?.toLowerCase() || "grocery"}`}>{symbols[product.category] || "📦"}</span>;
}

function TransactionList({ transactions }) {
  return <div className="transaction-list">{transactions.map((transaction) => <div className="transaction-row" key={transaction.id}><span className={`transaction-icon transaction-${transaction.type}`}>{transaction.type === "payment" ? <ArrowDownLeft size={16} /> : transaction.type === "credit" ? <Clock3 size={16} /> : <ShoppingBag size={16} />}</span><span className="transaction-copy"><strong>{transaction.title}</strong><small>{transaction.detail}</small></span><span className="transaction-amount"><strong className={transaction.type === "payment" ? "amount-green" : ""}>{transaction.type === "credit" ? "+" : ""}{money(transaction.amount)}</strong><small>{transaction.time}</small></span></div>)}</div>;
}

function Inventory() {
  const { data, setData } = useStore();
  const [searchParams] = useState(() => new URLSearchParams(window.location.search));
  const [query, setQuery] = useState(searchParams.get("search") || "");
  const [category, setCategory] = useState("All categories");
  const [showAdd, setShowAdd] = useState(false);
  const categories = ["All categories", ...new Set(data.products.map((product) => product.category))];
  const filtered = data.products.filter((product) => (product.name.toLowerCase().includes(query.toLowerCase()) || product.sku.toLowerCase().includes(query.toLowerCase())) && (category === "All categories" || product.category === category));
  const addProduct = (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const product = { id: `p${Date.now()}`, name: form.get("name"), category: form.get("category"), price: Number(form.get("price")), stock: Number(form.get("stock")), minStock: Number(form.get("minStock")), unit: form.get("unit"), sku: `NEW-${Date.now().toString().slice(-4)}` };
    setData((current) => ({ ...current, products: [product, ...current.products] }));
    setShowAdd(false);
  };
  return <div><PageIntro eyebrow="YOUR CATALOGUE" title="Inventory" description={`${data.products.length} products · Keep an eye on what’s on your shelves.`} action={<Button icon={Plus} onClick={() => setShowAdd(true)}>Add product</Button>} />
    <section className="panel table-panel"><div className="table-toolbar"><label className="table-search"><Search size={16} /><input placeholder="Search products..." value={query} onChange={(event) => setQuery(event.target.value)} /></label><div className="toolbar-right"><select className="select-button native-select" value={category} onChange={(event) => setCategory(event.target.value)}>{categories.map((item) => <option key={item}>{item}</option>)}</select><button className="select-button" onClick={() => setCategory("All categories")}><Filter size={14} /> Filters</button></div></div>
      <div className="table-scroll"><table><thead><tr><th>PRODUCT</th><th>SKU</th><th>CATEGORY</th><th>PRICE</th><th>IN STOCK</th><th>STATUS</th><th /></tr></thead><tbody>{filtered.map((product) => <tr key={product.id} className="clickable-row" onClick={() => window.location.assign(`/inventory/${product.id}`)}><td><div className="product-cell"><ProductThumb product={product} /><span><strong>{product.name}</strong><small>per {product.unit}</small></span></div></td><td className="muted-cell">{product.sku}</td><td><span className="category-chip">{product.category}</span></td><td className="strong-cell">{money(product.price)}</td><td><span className="stock-value">{product.stock} <small>{product.unit}s</small></span></td><td><StatusBadge low={product.stock <= product.minStock}>{product.stock <= product.minStock ? "Low stock" : "In stock"}</StatusBadge></td><td><button className="row-more" aria-label="More options"><Ellipsis size={18} /></button></td></tr>)}</tbody></table></div>
      {filtered.length === 0 && <EmptyState title="No products found" message="Try a different search or category." />}
      <div className="table-footer"><span>Showing <strong>{filtered.length}</strong> of <strong>{data.products.length}</strong> products</span><div className="pagination"><button disabled><ChevronLeft size={15} /></button><button className="page-current">1</button><button disabled><ChevronRight size={15} /></button></div></div>
    </section>
    {showAdd && <Modal title="Add a product" onClose={() => setShowAdd(false)}><form className="form-grid" onSubmit={addProduct}><label className="form-field full-field">Product name<input name="name" required placeholder="e.g. Amul Gold Milk" /></label><label className="form-field">Category<select name="category"><option>Grocery</option><option>Dairy</option><option>Snacks</option><option>Essentials</option><option>Household</option></select></label><label className="form-field">Unit<select name="unit"><option>packet</option><option>piece</option><option>kg</option><option>litre</option><option>pack</option></select></label><label className="form-field">Selling price<input name="price" type="number" min="0" required placeholder="₹ 0.00" /></label><label className="form-field">Current stock<input name="stock" type="number" min="0" required placeholder="0" /></label><label className="form-field full-field">Low stock alert at<input name="minStock" type="number" min="0" required defaultValue="10" /></label><div className="form-actions full-field"><Button variant="secondary" onClick={() => setShowAdd(false)}>Cancel</Button><Button type="submit">Add product</Button></div></form></Modal>}
  </div>;
}

function StatusBadge({ children, low = false }) { return <span className={`status-badge ${low ? "status-low" : "status-good"}`}><i />{children}</span>; }

function ProductDetail() {
  const { id } = useParams();
  const { data, updateProduct } = useStore();
  const product = data.products.find((item) => item.id === id);
  const [adjusting, setAdjusting] = useState(false);
  if (!product) return <EmptyState title="Product not found" message="This item may have been removed from your inventory." />;
  const adjust = (event) => { event.preventDefault(); const amount = Number(new FormData(event.currentTarget).get("amount")); updateProduct(id, (item) => ({ ...item, stock: Math.max(0, item.stock + amount) })); setAdjusting(false); };
  return <div><Link className="back-link" to="/inventory"><ArrowLeft size={15} /> Back to inventory</Link><PageIntro eyebrow={product.category.toUpperCase()} title={product.name} description={`Product details · ${product.sku}`} action={<Button variant="secondary" icon={Plus} onClick={() => setAdjusting(true)}>Adjust stock</Button>} /><div className="detail-grid"><section className="panel product-detail-card"><div className="product-detail-head"><ProductThumb product={product} large /><div><h2>{product.name}</h2><span className="category-chip">{product.category}</span></div></div><div className="detail-stats"><div><span>SELLING PRICE</span><strong>{money(product.price)} <small>/ {product.unit}</small></strong></div><div><span>CURRENT STOCK</span><strong>{product.stock} <small>{product.unit}s</small></strong></div><div><span>LOW STOCK ALERT</span><strong>{product.minStock} <small>{product.unit}s</small></strong></div><div><span>STOCK STATUS</span><StatusBadge low={product.stock <= product.minStock}>{product.stock <= product.minStock ? "Needs restock" : "Healthy"}</StatusBadge></div></div></section><section className="panel"><h2 className="panel-title">Stock activity</h2><div className="activity-empty"><div className="empty-icon"><Boxes size={20} /></div><strong>You're all caught up</strong><span>Stock updates from your assistant will show here.</span></div></section></div>{adjusting && <Modal title="Adjust stock" onClose={() => setAdjusting(false)}><form className="form-grid" onSubmit={adjust}><div className="full-field stock-current"><span>Current stock</span><strong>{product.stock} {product.unit}s</strong></div><label className="form-field full-field">Adjustment<input name="amount" type="number" required placeholder="Use a minus sign to remove stock" /></label><div className="form-actions full-field"><Button variant="secondary" onClick={() => setAdjusting(false)}>Cancel</Button><Button type="submit">Save adjustment</Button></div></form></Modal>}</div>;
}

function Customers() {
  const { data, setData } = useStore();
  const [query, setQuery] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const filtered = data.customers.filter((customer) => customer.name.toLowerCase().includes(query.toLowerCase()) || customer.phone.includes(query));
  const addCustomer = (event) => {
    event.preventDefault(); const form = new FormData(event.currentTarget); const name = form.get("name");
    const initials = name.trim().split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase();
    const customer = { id: `c${Date.now()}`, name, phone: form.get("phone"), due: 0, lastActive: "Just now", initials, color: "mint" };
    setData((current) => ({ ...current, customers: [customer, ...current.customers] })); setShowAdd(false);
  };
  return <div><PageIntro eyebrow="YOUR COMMUNITY" title="Customers" description="Good relationships make a good business. Keep them close." action={<Button icon={Plus} onClick={() => setShowAdd(true)}>Add customer</Button>} /><div className="customer-summary"><div className="summary-mini"><span className="summary-icon tone-green"><Users size={17} /></span><span><small>All customers</small><strong>{data.customers.length}</strong></span></div><div className="summary-mini"><span className="summary-icon tone-amber"><Wallet size={17} /></span><span><small>With outstanding Udhaar</small><strong>{data.customers.filter((item) => item.due > 0).length}</strong></span></div><div className="summary-mini"><span className="summary-icon tone-blue"><IndianRupee size={17} /></span><span><small>Total to collect</small><strong>{money(data.customers.reduce((sum, item) => sum + item.due, 0))}</strong></span></div></div>
    <section className="panel table-panel"><div className="table-toolbar"><label className="table-search"><Search size={16} /><input placeholder="Search customers..." value={query} onChange={(event) => setQuery(event.target.value)} /></label><button className="select-button"><ListFilter size={14} /> Filters</button></div><div className="table-scroll"><table><thead><tr><th>CUSTOMER</th><th>PHONE</th><th>OUTSTANDING</th><th>LAST ACTIVE</th><th /></tr></thead><tbody>{filtered.map((customer) => <tr key={customer.id} className="clickable-row" onClick={() => window.location.assign(`/customers/${customer.id}`)}><td><div className="customer-cell"><span className={`customer-avatar avatar-${customer.color}`}>{customer.initials}</span><strong>{customer.name}</strong></div></td><td className="muted-cell">{customer.phone}</td><td className={customer.due ? "due-value" : "muted-cell"}>{customer.due ? money(customer.due) : "All settled"}</td><td className="muted-cell">{customer.lastActive}</td><td><button className="row-more" aria-label="More options"><Ellipsis size={18} /></button></td></tr>)}</tbody></table></div><div className="table-footer"><span>Showing <strong>{filtered.length}</strong> customers</span></div></section>
    {showAdd && <Modal title="Add a customer" onClose={() => setShowAdd(false)}><form className="form-grid" onSubmit={addCustomer}><label className="form-field full-field">Customer name<input name="name" required placeholder="Full name" /></label><label className="form-field full-field">Mobile number<input name="phone" type="tel" required placeholder="+91 98765 43210" /></label><div className="form-actions full-field"><Button variant="secondary" onClick={() => setShowAdd(false)}>Cancel</Button><Button type="submit">Add customer</Button></div></form></Modal>}
  </div>;
}

function CustomerDetail() {
  const { id } = useParams();
  const { data, addTransaction, setData } = useStore();
  const customer = data.customers.find((item) => item.id === id);
  const [payment, setPayment] = useState(false);
  const [amount, setAmount] = useState("");
  if (!customer) return <EmptyState title="Customer not found" message="This customer may have been removed." />;
  const pay = (event) => {
    event.preventDefault(); const paid = Number(amount); if (paid <= 0) return;
    setData((current) => ({ ...current, customers: current.customers.map((item) => item.id === id ? { ...item, due: Math.max(0, item.due - paid) } : item) }));
    addTransaction({ customerId: id, title: "Udhaar payment received", detail: `${customer.name} · Cash`, amount: paid, type: "payment" }); setPayment(false); setAmount("");
  };
  const records = data.transactions.filter((item) => item.customerId === id);
  return <div><Link className="back-link" to="/customers"><ArrowLeft size={15} /> Back to customers</Link><div className="customer-profile-hero panel"><span className={`customer-avatar customer-avatar-xl avatar-${customer.color}`}>{customer.initials}</span><div className="customer-hero-copy"><h1>{customer.name}</h1><p>{customer.phone} <span>·</span> Customer since January 2025</p></div><Button icon={IndianRupee} variant="secondary" onClick={() => setPayment(true)}>Record payment</Button></div><div className="detail-grid customer-detail-grid"><section className="panel udhaar-balance-card"><span>OUTSTANDING BALANCE</span><strong>{money(customer.due)}</strong><p>{customer.due ? "A gentle reminder goes a long way." : "All settled up — what a lovely customer."}</p><Link to="/udhaar" className="text-link">View Udhaar book <ArrowRight size={14} /></Link></section><section className="panel"><div className="panel-heading"><div><h2>Recent activity</h2><p>Transactions for {customer.name.split(" ")[0]}</p></div></div>{records.length ? <TransactionList transactions={records} /> : <div className="activity-empty"><strong>No activity yet</strong><span>Transactions with this customer will appear here.</span></div>}</section></div>{payment && <Modal title="Record a payment" onClose={() => setPayment(false)}><form className="form-grid" onSubmit={pay}><p className="full-field modal-copy">Record a payment from <strong>{customer.name}</strong>. They owe {money(customer.due)}.</p><label className="form-field full-field">Amount received<input type="number" min="1" max={customer.due} value={amount} onChange={(event) => setAmount(event.target.value)} required placeholder="₹ 0.00" /></label><div className="form-actions full-field"><Button variant="secondary" onClick={() => setPayment(false)}>Cancel</Button><Button type="submit">Record payment</Button></div></form></Modal>}</div>;
}

function Udhaar() {
  const { data } = useStore();
  const totalDue = data.customers.reduce((sum, item) => sum + item.due, 0);
  const dueCustomers = data.customers.filter((item) => item.due > 0).sort((a, b) => b.due - a.due);
  return <div><PageIntro eyebrow="CUSTOMER CREDIT" title="Udhaar book" description="A clear picture of what’s owed, and who’s got your back." action={<Button icon={MessageCircle} onClick={() => window.location.assign("/assistant")}>Ask your assistant</Button>} /><div className="udhaar-overview"><div className="udhaar-total"><span className="udhaar-total-icon"><Wallet size={19} /></span><span><small>Total outstanding</small><strong>{money(totalDue)}</strong><em>Across {dueCustomers.length} customers</em></span><div className="udhaar-trend"><TrendingDown size={15} /> 8% this month</div></div><div className="udhaar-stat"><span>Collected this month</span><strong>₹8,450</strong><small><span className="trend-positive">↑ 12%</span> vs last month</small></div><div className="udhaar-stat"><span>Average credit</span><strong>₹842</strong><small>Per customer</small></div></div><section className="panel table-panel"><div className="panel-heading panel-heading-padded"><div><h2>Customers with balance</h2><p>Follow up when it feels right.</p></div><button className="select-button"><CalendarDays size={14} /> This month <ChevronDown size={14} /></button></div><div className="table-scroll"><table><thead><tr><th>CUSTOMER</th><th>PHONE</th><th>LAST ACTIVITY</th><th>AMOUNT DUE</th><th /></tr></thead><tbody>{dueCustomers.map((customer) => <tr className="clickable-row" key={customer.id} onClick={() => window.location.assign(`/customers/${customer.id}`)}><td><div className="customer-cell"><span className={`customer-avatar avatar-${customer.color}`}>{customer.initials}</span><strong>{customer.name}</strong></div></td><td className="muted-cell">{customer.phone}</td><td className="muted-cell">{customer.lastActive}</td><td className="due-value">{money(customer.due)}</td><td><Link to={`/customers/${customer.id}`} className="text-link small-link">View <ArrowRight size={13} /></Link></td></tr>)}</tbody></table></div><div className="udhaar-note"><ShieldCheck size={16} /><span>Every rupee is tracked privately and securely on this device.</span></div></section></div>;
}

function Transactions() {
  const { data } = useStore();
  const [filter, setFilter] = useState("All activity");
  const filters = ["All activity", "Sales", "Udhaar", "Payments"];
  const filtered = data.transactions.filter((transaction) => filter === "All activity" || filter === "Sales" && transaction.type === "sale" || filter === "Udhaar" && transaction.type === "credit" || filter === "Payments" && transaction.type === "payment");
  return <div><PageIntro eyebrow="MONEY IN MOTION" title="Transactions" description="Every sale, payment and Udhaar — all in one place." action={<Button variant="secondary" icon={Download} onClick={() => window.print()}>Export</Button>} /><section className="panel table-panel"><div className="transaction-filters">{filters.map((item) => <button key={item} onClick={() => setFilter(item)} className={`filter-tab ${filter === item ? "selected" : ""}`}>{item}</button>)}</div><div className="table-scroll"><table><thead><tr><th>TRANSACTION</th><th>TYPE</th><th>DATE & TIME</th><th>AMOUNT</th></tr></thead><tbody>{filtered.map((item) => <tr key={item.id}><td><div className="product-cell"><span className={`transaction-icon transaction-${item.type}`}>{item.type === "payment" ? <ArrowDownLeft size={16} /> : item.type === "credit" ? <Clock3 size={16} /> : <ShoppingBag size={16} />}</span><span><strong>{item.title}</strong><small>{item.detail}</small></span></div></td><td><span className={`type-chip type-${item.type}`}>{item.type === "credit" ? "Udhaar" : item.type === "payment" ? "Payment" : "Sale"}</span></td><td className="muted-cell">{item.date}, {item.time}</td><td className={`strong-cell ${item.type === "payment" ? "amount-green" : ""}`}>{item.type === "credit" ? "+" : ""}{money(item.amount)}</td></tr>)}</tbody></table></div><div className="table-footer"><span>Showing <strong>{filtered.length}</strong> transactions</span></div></section></div>;
}

function Reports() {
  return <div><PageIntro eyebrow="A LITTLE PERSPECTIVE" title="Reports" description="Your business, at a glance. Better decisions start here." action={<button className="select-button"><CalendarDays size={14} /> Last 7 days <ChevronDown size={14} /></button>} /><div className="stat-grid report-stat-grid"><StatCard label="Total sales" value="₹28,640" note="vs. ₹24,180 last week" trend="+18.4%" icon={IndianRupee} tone="green" /><StatCard label="Items sold" value="342" note="Across 78 transactions" trend="+9.2%" icon={ShoppingBag} tone="blue" /><StatCard label="Udhaar collected" value="₹8,450" note="From 14 payments" trend="+12%" icon={Wallet} tone="amber" /><StatCard label="Top category" value="Grocery" note="42% of your sales" icon={TrendingUp} tone="rose" /></div><section className="panel report-panel"><div className="panel-heading"><div><h2>Sales performance</h2><p>A steady week is a good week.</p></div><span className="chart-legend"><i /> Sales</span></div><SalesChart /></section><div className="dashboard-bottom-grid report-bottom"><section className="panel"><div className="panel-heading"><div><h2>Top-selling products</h2><p>Your customers' favourites</p></div></div><div className="top-product-list">{[["Maggi 2-Minute Noodles", "84 packets sold", "₹1,176"], ["Amul Taaza Milk", "62 packets sold", "₹1,736"], ["Parle-G Biscuits", "48 packets sold", "₹480"], ["Tata Salt", "31 packets sold", "₹744"]].map((row, i) => <div className="top-product-row" key={row[0]}><span className="rank-number">0{i + 1}</span><span><strong>{row[0]}</strong><small>{row[1]}</small></span><b>{row[2]}</b></div>)}</div></section><section className="panel insight-panel"><div className="insight-icon"><Sparkles size={18} /></div><div className="eyebrow">A QUICK INSIGHT</div><h2>You're growing steadily.</h2><p>Your sales are up 18% this week. Milk and everyday grocery items are bringing most customers through the door.</p><Link to="/assistant" className="text-link">Ask your assistant <ArrowRight size={14} /></Link></section></div></div>;
}

function LowStock() {
  const { data } = useStore();
  const lowProducts = data.products.filter((product) => product.stock <= product.minStock);
  return <div><PageIntro eyebrow="A FRIENDLY HEADS-UP" title="Stock to watch" description="A few products are running low. Let’s get ahead of the next busy day." action={<Button icon={MessageCircle} onClick={() => window.location.assign("/assistant")}>Ask to restock</Button>} /><div className="alert-banner"><span className="alert-banner-icon"><AlertTriangle size={17} /></span><span><strong>{lowProducts.length} products need a little attention</strong><small>Stock up before they run out. Your customers will thank you.</small></span></div><section className="panel table-panel"><div className="panel-heading panel-heading-padded"><div><h2>Running low</h2><p>Based on your minimum stock levels.</p></div><span className="low-count">{lowProducts.length} items</span></div><div className="low-stock-list">{lowProducts.map((product) => <div className="low-stock-row" key={product.id}><ProductThumb product={product} /><div className="low-product-name"><strong>{product.name}</strong><small>{product.category} · {money(product.price)} per {product.unit}</small></div><div className="low-stock-progress"><div className="progress-label"><span>Current stock</span><strong>{product.stock} <small>/ {product.minStock} {product.unit}s</small></strong></div><div className="progress-track"><span style={{ width: `${Math.min(product.stock / product.minStock * 100, 100)}%` }} /></div></div><span className="restock-chip">{product.stock === 0 ? "Out of stock" : "Low"}</span><Link className="icon-button subtle-icon" to={`/inventory/${product.id}`} aria-label={`View ${product.name}`}><ArrowRight size={16} /></Link></div>)}</div><div className="reorder-hint"><Sparkles size={16} /><span><strong>Quick tip</strong> — say “Received 20 milk packets” to update stock in seconds.</span><Link to="/assistant" className="text-link">Try it <ArrowRight size={14} /></Link></div></section></div>;
}

function SettingsPage() {
  const { data, setData } = useStore();
  const [saved, setSaved] = useState(false);
  const submit = (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); setData((current) => ({ ...current, shop: { ...current.shop, name: form.get("shop"), owner: form.get("owner"), phone: form.get("phone"), city: form.get("city"), address: form.get("address") } })); setSaved(true); setTimeout(() => setSaved(false), 2400); };
  return <div><PageIntro eyebrow="YOUR SPACE" title="Settings" description="Make Kirana Ledger feel a little more like your shop." /><div className="settings-layout"><aside className="settings-menu"><a className="settings-menu-item selected"><ShoppingBag size={16} /> Shop profile</a><a className="settings-menu-item"><UserRound size={16} /> Your account</a><a className="settings-menu-item"><Bell size={16} /> Notifications</a><a className="settings-menu-item"><ShieldCheck size={16} /> Privacy & security</a></aside><form className="panel settings-form" onSubmit={submit}><div className="panel-heading"><div><h2>Shop profile</h2><p>These details help personalise your experience.</p></div></div><label className="form-field">Shop name<input name="shop" defaultValue={data.shop.name} required /></label><label className="form-field">Owner name<input name="owner" defaultValue={data.shop.owner} required /></label><label className="form-field">Mobile number<input name="phone" defaultValue={data.shop.phone} /></label><label className="form-field">City<input name="city" defaultValue={data.shop.city} /></label><label className="form-field">Shop address<input name="address" defaultValue={data.shop.address} /></label><div className="settings-footer"><span className="saved-note">{saved && <><Check size={15} /> Changes saved</>}</span><Button type="submit">Save changes</Button></div></form></div></div>;
}

function Assistant() {
  const { data, setData, addTransaction, refreshBackend } = useStore();
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [data.messages]);

  const processMessage = async (raw) => {
    const text = raw.trim();
    if (!text) return;

    const userMessage = { id: `m${Date.now()}`, role: "user", text };
    setData((current) => ({ ...current, messages: [...current.messages, userMessage] }));
    setInput("");
    setBusy(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      if (res.ok) {
        const payload = await res.json();
        const replyText = payload.reply || "Done.";
        const assistantMessage = { id: `m${Date.now()}-reply`, role: "assistant", text: replyText };
        setData((current) => ({ ...current, messages: [...current.messages, assistantMessage] }));

        if (payload.success) {
          if (payload.inventory_updates && payload.inventory_updates.length > 0) {
            payload.inventory_updates.forEach((u) => {
              addTransaction({
                title: `${u.item_name} ${u.action}`,
                detail: `${u.quantity} ${u.unit} · Stock: ${u.previous_stock} → ${u.resulting_stock}`,
                amount: 0,
                type: u.action === "sold" ? "sale" : "restock",
              });
            });
          }
          if (payload.credit_update) {
            const cu = payload.credit_update;
            addTransaction({
              customerId: String(cu.customer_name),
              title: cu.action === "payment" ? "Udhaar payment received" : "Udhaar added",
              detail: `${cu.customer_name} · Resulting balance: ₹${cu.resulting_balance}`,
              amount: cu.amount,
              type: cu.action === "payment" ? "payment" : "credit",
            });
          }
          await refreshBackend();
        }
      } else {
        const errPayload = await res.json().catch(() => ({}));
        const replyText = errPayload.detail || "Sorry, I could not process that request.";
        const assistantMessage = { id: `m${Date.now()}-reply`, role: "assistant", text: replyText };
        setData((current) => ({ ...current, messages: [...current.messages, assistantMessage] }));
      }
    } catch (error) {
      console.error("Chat backend connection error:", error);
      const assistantMessage = {
        id: `m${Date.now()}-reply`,
        role: "assistant",
        text: "Could not connect to Kirana Ledger backend API. Please make sure the backend is running at http://127.0.0.1:8000.",
      };
      setData((current) => ({ ...current, messages: [...current.messages, assistantMessage] }));
    } finally {
      setBusy(false);
    }
  };

  return <div className="assistant-page"><div className="assistant-heading"><div><div className="eyebrow">YOUR SHOP ASSISTANT</div><h1>What can I help with?</h1><p>A simple message is all it takes to keep your shop in good shape.</p></div><span className="assistant-online"><i /> Here for you</span></div><div className="assistant-workspace"><aside className="assistant-side"><div className="assistant-side-title"><Sparkles size={17} /> Try asking</div><p>Say it just like you’d say it to a friend.</p>{["Sold 5 Maggi", "Received 20 milk packets", "Ramesh paid ₹500", "Which products are low?", "Show today's sales"].map((suggestion) => <button className="suggestion-button" key={suggestion} onClick={() => processMessage(suggestion)}><MessageCircle size={15} />{suggestion}<ArrowRight size={14} /></button>)}<div className="assistant-privacy"><ShieldCheck size={15} /><span>Your shop data stays private on this device.</span></div></aside><section className="assistant-chat"><div className="chat-topline"><span className="assistant-bot-avatar"><Sparkles size={17} /></span><span><strong>Kirana Assistant</strong><small><i /> Online · ready when you are</small></span><button className="icon-button chat-menu" aria-label="More"><Ellipsis size={19} /></button></div><div className="chat-messages">{data.messages.length === 0 && <div className="chat-welcome"><div className="assistant-welcome-icon"><MessageCircle size={23} /></div><span className="eyebrow">YOUR EVERYDAY SHOP PARTNER</span><h2>Namaste, Ramesh!</h2><p>Your shop is in good hands. Ask me about your stock, record a sale, or just check in on your business.</p><div className="welcome-prompts">{["How much Maggi do I have?", "Who owes me money?"].map((prompt) => <button key={prompt} onClick={() => processMessage(prompt)}>{prompt}<ArrowRight size={14} /></button>)}</div></div>}{data.messages.map((message) => <div className={`chat-message message-${message.role}`} key={message.id}>{message.role === "assistant" && <span className="message-avatar"><Sparkles size={13} /></span>}<div className="message-bubble">{message.text}<small>{message.role === "user" ? "You · just now" : "Kirana Assistant · just now"}</small></div>{message.role === "user" && <span className="message-user-avatar">RS</span>}</div>)}{busy && <div className="chat-message message-assistant"><span className="message-avatar"><Sparkles size={13} /></span><div className="typing-indicator"><i /><i /><i /></div></div>}<div ref={bottomRef} /></div><form className="chat-composer" onSubmit={(event) => { event.preventDefault(); processMessage(input); }}><input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Tell me what happened at your shop..." /><button className="composer-mic" type="button" aria-label="Voice input"><Mic size={18} /></button><button className="send-button" type="submit" disabled={!input.trim() || busy} aria-label="Send message"><Send size={17} /></button><span className="composer-note">Press enter to send</span></form></section></div></div>;
}

function Login() {
  const navigate = useNavigate();
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [otpOpen, setOtpOpen] = useState(false);
  const [otp, setOtp] = useState("");
  const [otpError, setOtpError] = useState("");
  const [resetOpen, setResetOpen] = useState(false);
  const [resetNotice, setResetNotice] = useState("");
  const validContact = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) || /^\+?[\d\s()-]{10,15}$/.test(value);
  const submit = (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const contact = String(form.get("email") || "").trim();
    const password = String(form.get("password") || "");
    const nextErrors = {};
    if (!contact) nextErrors.email = "Please enter your mobile number or email.";
    else if (!validContact(contact)) nextErrors.email = "Please enter a valid mobile number or email.";
    if (!password) nextErrors.password = "Please enter your password.";
    else if (password.length < 6) nextErrors.password = "Password must be at least 6 characters.";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    setLoading(true);
    window.setTimeout(() => { sessionStorage.setItem("kirana-ledger-demo-session", "1"); navigate("/dashboard"); }, 350);
  };
  const verifyOtp = (event) => {
    event.preventDefault();
    if (otp !== "123456") { setOtpError("That code didn’t match. For this demo, use 123456."); return; }
    sessionStorage.setItem("kirana-ledger-demo-session", "1");
    navigate("/dashboard");
  };
  const requestReset = (event) => { event.preventDefault(); setResetNotice("Demo only — password reset will be connected to the backend later."); };
  return <div className="auth-page"><div className="auth-brand-panel"><Brand /><div className="auth-story"><span className="eyebrow">MADE FOR YOUR SHOP</span><h1>Run your shop<br />by simply <span>talking to it.</span></h1><p>Track inventory, monitor low-stock products, understand daily activity and manage supplier reorders from one simple dashboard.</p><div className="auth-feature-list"><span><Check size={14} /> Simple inventory management</span><span><Check size={14} /> Smart low-stock alerts</span><span><Check size={14} /> Daily shop activity</span><span><Check size={14} /> Faster supplier reordering</span></div><div className="auth-story-note"><span className="auth-note-icon"><MessageCircle size={17} /></span><span>“Sold 5 Maggi”<small>That's all it takes.</small></span></div></div><div className="auth-footer">Trusted by local shops, built for the way you work.</div></div><div className="auth-form-panel"><div className="auth-mobile-brand"><Brand /></div><form className="auth-card" onSubmit={submit} noValidate><div className="auth-heading"><div className="eyebrow">WELCOME BACK</div><h2>Welcome back</h2><p>Sign in to your shop dashboard.</p></div><label className="form-field" htmlFor="login-contact">Mobile / Email<input id="login-contact" name="email" type="text" autoComplete="username" aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? "login-contact-error" : undefined} placeholder="Enter your mobile number or email" onChange={() => setErrors((current) => ({ ...current, email: undefined }))} />{errors.email && <span className="field-error" id="login-contact-error" role="alert">{errors.email}</span>}</label><label className="form-field" htmlFor="login-password">Password<div className="password-input"><input id="login-password" name="password" type={passwordVisible ? "text" : "password"} autoComplete="current-password" aria-invalid={Boolean(errors.password)} aria-describedby={errors.password ? "login-password-error" : undefined} placeholder="Enter your password" onChange={() => setErrors((current) => ({ ...current, password: undefined }))} /><button type="button" className="password-toggle" aria-label={passwordVisible ? "Hide password" : "Show password"} onClick={() => setPasswordVisible((current) => !current)}>{passwordVisible ? <EyeOff size={16} /> : <Eye size={16} />}</button></div>{errors.password && <span className="field-error" id="login-password-error" role="alert">{errors.password}</span>}<button type="button" className="forgot-link" onClick={() => { setResetNotice(""); setResetOpen(true); }}>Forgot password?</button></label><Button type="submit" className="auth-submit">{loading ? "Signing in..." : "Sign In"}{!loading && <ArrowRight size={16} />}</Button><div className="auth-divider"><span />or<span /></div><Button variant="secondary" className="otp-button" icon={MessageCircle} onClick={() => { setOtp(""); setOtpError(""); setOtpOpen(true); }}>Continue with OTP</Button><div className="auth-signup">Don't have an account? <Link to="/onboarding">Create one</Link></div><div className="demo-caption">Frontend demo · Any valid-looking mobile/email and password (6+ characters)</div></form><span className="auth-legal">By continuing, you agree to our Terms of Service and Privacy Policy.</span></div>
    {otpOpen && <Modal title="Verify your number" onClose={() => setOtpOpen(false)}><form className="form-grid" onSubmit={verifyOtp}><p className="full-field modal-copy">We’ve sent a verification code to your mobile number. <span className="demo-caption">Demo code: 123456</span></p><label className="form-field full-field" htmlFor="demo-otp">Verification code<input id="demo-otp" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={otp} onChange={(event) => { setOtp(event.target.value.replace(/\D/g, "")); setOtpError(""); }} placeholder="_ _ _ _ _ _" aria-invalid={Boolean(otpError)} aria-describedby={otpError ? "otp-error" : undefined} required />{otpError && <span className="field-error" id="otp-error" role="alert">{otpError}</span>}</label><div className="form-actions full-field"><Button variant="secondary" onClick={() => setOtpOpen(false)}>Cancel</Button><Button type="submit">Verify</Button></div></form></Modal>}
    {resetOpen && <Modal title="Reset your password" onClose={() => setResetOpen(false)}><form className="form-grid" onSubmit={requestReset}><label className="form-field full-field" htmlFor="reset-contact">Mobile / Email<input id="reset-contact" required placeholder="Enter your mobile number or email" /></label>{resetNotice && <p className="full-field reset-notice" role="status">{resetNotice}</p>}<div className="form-actions full-field"><Button variant="secondary" onClick={() => setResetOpen(false)}>Cancel</Button><Button type="submit">Send Reset Link</Button></div></form></Modal>}
  </div>;
}

function Onboarding() {
  const { data, setData } = useStore();
  const [step, setStep] = useState(1);
  const [products, setProducts] = useState([{ name: "", category: "Grocery", price: "", stock: "", minStock: "10", unit: "packet" }]);
  const navigate = useNavigate();
  const saveShop = (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); setData((current) => ({ ...current, shop: { name: form.get("shop"), owner: form.get("owner"), phone: form.get("phone"), city: form.get("city"), address: form.get("address") } })); setStep(2); };
  const finish = () => { const added = products.filter((p) => p.name.trim()).map((p, index) => ({ ...p, id: `onboard-${Date.now()}-${index}`, price: Number(p.price || 0), stock: Number(p.stock || 0), minStock: Number(p.minStock || 10), sku: `NEW-${index + 1}` })); setData((current) => ({ ...current, products: added.length ? [...added, ...current.products] : current.products, onboardingComplete: true })); setStep(3); };
  return <div className="onboarding-page"><div className="onboarding-top"><Brand /><Link to="/login" className="skip-link">Already have an account? <strong>Sign in</strong></Link></div><div className="onboarding-content"><div className="onboarding-progress"><span className={`progress-step ${step >= 1 ? "active" : ""}`}><i>{step > 1 ? <Check size={14} /> : "1"}</i><span>Your shop</span></span><span className="progress-line" /><span className={`progress-step ${step >= 2 ? "active" : ""}`}><i>{step > 2 ? <Check size={14} /> : "2"}</i><span>First products</span></span><span className="progress-line" /><span className={`progress-step ${step >= 3 ? "active" : ""}`}><i>3</i><span>All set</span></span></div>
    {step === 1 && <form className="onboarding-card" onSubmit={saveShop}><span className="onboarding-icon"><ShoppingBag size={20} /></span><span className="eyebrow">LET'S GET YOU SET UP · STEP 1 OF 3</span><h1>Tell us about your shop</h1><p>A few details make your experience feel right at home.</p><div className="form-grid"><label className="form-field full-field">Shop name<input name="shop" required defaultValue={data.shop.name} placeholder="e.g. Sharma General Store" /></label><label className="form-field">Your name<input name="owner" required defaultValue={data.shop.owner} placeholder="Full name" /></label><label className="form-field">Mobile number<input name="phone" type="tel" required defaultValue={data.shop.phone} placeholder="+91 98765 43210" /></label><label className="form-field">City<input name="city" required defaultValue={data.shop.city} placeholder="e.g. Pune" /></label><label className="form-field">Shop address<input name="address" defaultValue={data.shop.address} placeholder="Area, street, city" /></label></div><Button type="submit" className="onboarding-next">Continue <ArrowRight size={16} /></Button><div className="onboarding-safe"><ShieldCheck size={14} /> Your shop details stay private and secure.</div></form>}
    {step === 2 && <div className="onboarding-card onboarding-products"><span className="onboarding-icon"><Package size={20} /></span><span className="eyebrow">LET'S GET YOU SET UP · STEP 2 OF 3</span><h1>Add your first products</h1><p>Start with a few favourites. You can always add more later.</p><div className="onboard-product-label"><span>PRODUCT DETAILS</span><button className="text-link" onClick={() => setProducts((current) => [...current, { name: "", category: "Grocery", price: "", stock: "", minStock: "10", unit: "packet" }])}><Plus size={14} /> Add another</button></div>{products.map((product, index) => <div className="onboard-product-row" key={index}><label className="form-field">Product name<input value={product.name} onChange={(event) => setProducts((current) => current.map((p, i) => i === index ? { ...p, name: event.target.value } : p))} placeholder="e.g. Amul Taaza Milk" /></label><label className="form-field">Category<select value={product.category} onChange={(event) => setProducts((current) => current.map((p, i) => i === index ? { ...p, category: event.target.value } : p))}><option>Grocery</option><option>Dairy</option><option>Snacks</option><option>Essentials</option><option>Household</option></select></label><div className="form-grid onboard-small-fields"><label className="form-field">Price<input type="number" min="0" value={product.price} onChange={(event) => setProducts((current) => current.map((p, i) => i === index ? { ...p, price: event.target.value } : p))} placeholder="₹ 0" /></label><label className="form-field">Stock<input type="number" min="0" value={product.stock} onChange={(event) => setProducts((current) => current.map((p, i) => i === index ? { ...p, stock: event.target.value } : p))} placeholder="0" /></label><label className="form-field">Min. stock<input type="number" min="0" value={product.minStock} onChange={(event) => setProducts((current) => current.map((p, i) => i === index ? { ...p, minStock: event.target.value } : p))} /></label><label className="form-field">Unit<select value={product.unit} onChange={(event) => setProducts((current) => current.map((p, i) => i === index ? { ...p, unit: event.target.value } : p))}><option>packet</option><option>piece</option><option>kg</option><option>litre</option></select></label></div></div>)}<div className="onboarding-actions"><Button variant="secondary" onClick={() => setStep(1)}><ArrowLeft size={15} /> Back</Button><Button onClick={finish}>Continue <ArrowRight size={16} /></Button></div><button className="skip-products" onClick={finish}>Skip for now</button></div>}
    {step === 3 && <div className="onboarding-card ready-card"><span className="ready-check"><Check size={27} /></span><span className="eyebrow">ALL DONE · YOU'RE READY</span><h1>Your shop is ready to go.</h1><p>Your shop is ready. Start managing it through Kirana Ledger.</p><div className="ready-summary"><span className="shop-avatar">SG</span><span><strong>{data.shop.name}</strong><small>{data.shop.city} · {products.filter((p) => p.name.trim()).length} products added</small></span><CheckCheck size={19} /></div><Button className="onboarding-next" onClick={() => navigate("/dashboard")}>Open Dashboard <ArrowRight size={16} /></Button></div>}
  </div><div className="onboarding-footer">Made with care for the people who keep our neighbourhoods running.</div></div>;
}

function Modal({ title, children, onClose }) {
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><div className="modal-card" role="dialog" aria-modal="true" aria-label={title}><div className="modal-header"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={18} /></button></div>{children}</div></div>;
}

function EmptyState({ title, message }) { return <div className="empty-state"><span className="empty-icon"><Package size={21} /></span><h2>{title}</h2><p>{message}</p></div>; }

function AppRoutes() {
  const location = useLocation();
  const authRoute = location.pathname === "/login" || location.pathname === "/onboarding";
  if (location.pathname === "/") return <Navigate to={sessionStorage.getItem("kirana-ledger-demo-session") ? "/dashboard" : "/login"} replace />;
  return authRoute ? <Routes><Route path="/login" element={<Login />} /><Route path="/onboarding" element={<Onboarding />} /><Route path="*" element={<Navigate to="/login" replace />} /></Routes> : <AppShell />;
}

export default function App() {
  return <StoreProvider><AppRoutes /></StoreProvider>;
}
