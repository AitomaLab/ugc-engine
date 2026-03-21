'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import Select from '@/components/ui/Select';
import ProductModal from '@/components/ui/ProductModal';
import MediaPreviewModal from '@/components/ui/MediaPreviewModal';
import { apiFetch } from '@/lib/utils';
import { Product } from '@/lib/types';
import { useProgressiveList } from '@/hooks/useProgressiveList';

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [previewAssetUrl, setPreviewAssetUrl] = useState<string | null>(null);

  async function handleDelete(id: string) {
    if (!confirm('Delete this product? This cannot be undone.')) return;
    try {
      await apiFetch(`/api/products/${id}`, { method: 'DELETE' });
      setProducts(prev => prev.filter(p => p.id !== id));
    } catch (err) { console.error('Delete error:', err); }
  }

  const handleOpenModal = (product?: Product) => {
    setSelectedProduct(product || null);
    setIsModalOpen(true);
  };

  const fetchProducts = useCallback(async () => {
    try {
      const data = await apiFetch<Product[]>('/api/products');
      setProducts(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  // Re-fetch when user switches projects
  useEffect(() => {
    const handler = () => { setLoading(true); fetchProducts(); };
    window.addEventListener('projectChanged', handler);
    return () => window.removeEventListener('projectChanged', handler);
  }, [fetchProducts]);

  const filtered = products.filter(p =>
    (p.name || '').toLowerCase().includes(search.toLowerCase()) &&
    (typeFilter === '' || (p.type ?? '').toLowerCase() === typeFilter.toLowerCase())
  );

  const { visibleItems: visibleProducts, sentinelRef, hasMore } = useProgressiveList(filtered, 12);

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
          <Select
            className='filter-select'
            value={typeFilter}
            onChange={setTypeFilter}
            options={[
              { value: '', label: 'All Types' },
              { value: 'physical', label: 'Physical' },
              { value: 'digital', label: 'Digital' }
            ]}
          />
        </div>
        <button className='btn-create' onClick={() => handleOpenModal()}>
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
          <button className='btn-primary' onClick={() => handleOpenModal()}>Add Product</button>
        </div>
      ) : (
        <>
        <div className='products-grid'>
          {visibleProducts.map(product => (
            <div key={product.id} className='product-card'>
              <div
                className='product-img'
                onClick={() => product.image_url && setPreviewAssetUrl(product.image_url)}
                style={{ cursor: product.image_url ? 'zoom-in' : 'default', position: 'relative' }}
              >
                <button className="card-delete-btn" onClick={(e) => { e.stopPropagation(); handleDelete(product.id); }} title="Delete product">
                  <svg viewBox="0 0 24 24"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
                </button>
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
                <Link href={`/cinematic?product_id=${product.id}`} className='product-btn primary' style={{ textDecoration: 'none' }}>
                  <svg viewBox='0 0 24 24'><rect x='2' y='2' width='20' height='20' rx='2.18' ry='2.18' /><line x1='7' y1='2' x2='7' y2='22' /><line x1='17' y1='2' x2='17' y2='22' /><line x1='2' y1='12' x2='22' y2='12' /><line x1='2' y1='7' x2='7' y2='7' /><line x1='2' y1='17' x2='7' y2='17' /><line x1='17' y1='7' x2='22' y2='7' /><line x1='17' y1='17' x2='22' y2='17' /></svg>
                  Cinematic
                </Link>
                <Link href={`/create?product_id=${product.id}`} className='product-btn secondary' style={{ textDecoration: 'none' }}>
                  <svg viewBox='0 0 24 24'><polygon points='5,3 19,12 5,21' /></svg>
                  Create
                </Link>
                <button onClick={() => handleOpenModal(product)} className='product-btn secondary' style={{ flex: '0 0 auto', padding: '10px' }} title="Edit Product">
                  <svg viewBox="0 0 24 24"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" /></svg>
                </button>
              </div>
            </div>
          ))}
        </div>
        {hasMore && <div ref={sentinelRef} style={{ height: '1px', marginTop: '8px' }} />}
        </>
      )}

      {isModalOpen && (
        <ProductModal
          isOpen={isModalOpen}
          product={selectedProduct}
          onClose={() => setIsModalOpen(false)}
          onSave={() => { fetchProducts(); }}
        />
      )}

      <MediaPreviewModal
        isOpen={!!previewAssetUrl}
        onClose={() => setPreviewAssetUrl(null)}
        src={previewAssetUrl || ''}
        type="image"
      />
    </div>
  );
}
