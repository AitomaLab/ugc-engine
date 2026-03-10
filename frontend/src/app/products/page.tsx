'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/utils';
import { Product } from '@/lib/types';

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  const fetchProducts = useCallback(async () => {
    try {
      const data = await apiFetch<Product[]>('/api/products');
      setProducts(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  const filtered = products.filter(p =>
    (p.name || '').toLowerCase().includes(search.toLowerCase()) &&
    (typeFilter === '' || (p.type ?? '').toLowerCase() === typeFilter.toLowerCase())
  );

  return (
    <div className='content-area'>
      <div className='page-header'>
        <h1>Products</h1>
        <p>Manage the products used in your UGC campaigns.</p>
      </div>

      <div className='asset-toolbar'>
        <div className='asset-toolbar-left'>
          <div className='search-box'>
            <svg viewBox='0 0 24 24'><circle cx='11' cy='11' r='8' /><line x1='21' y1='21' x2='16.65' y2='16.65' /></svg>
            <input type='text' placeholder='Search products...' value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className='filter-select' value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
            <option value=''>All Types</option>
            <option value='physical'>Physical</option>
            <option value='digital'>Digital</option>
          </select>
        </div>
        <button className='btn-create' onClick={() => {/* open product upload modal */ }}>
          <svg viewBox='0 0 24 24'><line x1='12' y1='5' x2='12' y2='19' /><line x1='5' y1='12' x2='19' y2='12' /></svg>
          Add Product
        </button>
      </div>

      {loading ? (
        <div className='empty-state'><div className='empty-title'>Loading products...</div></div>
      ) : filtered.length === 0 ? (
        <div className='empty-state'>
          <div className='empty-icon'>
            <svg viewBox='0 0 24 24'><path d='M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z' /></svg>
          </div>
          <div className='empty-title'>No products yet</div>
          <div className='empty-sub'>Add a product to start creating UGC videos.</div>
          <button className='btn-primary'>Add Product</button>
        </div>
      ) : (
        <div className='products-grid'>
          {filtered.map(product => (
            <div key={product.id} className='product-card'>
              <div className='product-img'>
                {product.image_url ? (
                  <img src={product.image_url} alt={product.name} />
                ) : (
                  <svg viewBox='0 0 24 24'><path d='M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z' /></svg>
                )}
              </div>
              <div className='product-info'>
                <div className='product-name'>{product.name}</div>
                <div className='product-meta'>{product.type ?? 'Product'} · {product.job_count ?? 0} videos generated</div>
              </div>
              <div className='product-actions'>
                <Link href={`/cinematic?product_id=${product.id}`} className='product-btn primary'>
                  <svg viewBox='0 0 24 24'><path d='M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4' /><polyline points='10 17 15 12 10 7' /></svg>
                  Cinematic
                </Link>
                <Link href={`/create?product_id=${product.id}`} className='product-btn secondary'>
                  <svg viewBox='0 0 24 24'><polygon points='5,3 19,12 5,21' /></svg>
                  Create
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
