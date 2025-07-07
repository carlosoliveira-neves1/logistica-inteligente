from flask import Blueprint, request, jsonify, send_file
from flask_cors import cross_origin
import io
import os
from datetime import datetime

logistics_bp = Blueprint('logistics', __name__)

# Global variable to store the last suggestions for export
last_suggestions = []

@logistics_bp.route('/upload', methods=['POST'])
@cross_origin()
def upload_file():
    global last_suggestions
    
    try:
        # Import pandas here to avoid deployment issues
        import pandas as pd
        import numpy as np
        
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo foi enviado'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo foi selecionado'}), 400
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({'error': 'Apenas arquivos Excel são aceitos'}), 400
        
        # Read the Excel file
        df = pd.read_excel(file, header=None, engine='openpyxl')
        
        # Find the row with store names (looking for "LJ 1Mega Loja")
        store_names_row_index = -1
        for i, row in df.iterrows():
            if any('LJ 1Mega Loja' in str(cell) for cell in row.values):
                store_names_row_index = i
                break
        
        if store_names_row_index == -1:
            return jsonify({'error': 'Não foi possível encontrar os dados das lojas na planilha. Certifique-se de que a planilha contém as lojas no formato esperado.'}), 400
        
        # Process the data
        data_header_row_index = store_names_row_index + 1
        
        # Extract data rows (skip header rows and sub-group rows)
        data_df = df.iloc[data_header_row_index + 1:].copy()
        
        # Filter out non-product rows (sub-group headers, etc.)
        # Keep only rows that have a numeric product code in the first column
        data_df = data_df[data_df.iloc[:, 0].apply(lambda x: str(x).replace('-', '').isdigit() if pd.notna(x) else False)]
        
        # Remove rows where the first column is empty or NaN
        data_df = data_df.dropna(subset=[data_df.columns[0]])
        
        # Generate transfer suggestions
        suggestions = generate_transfer_suggestions(data_df)
        
        # Store suggestions globally for export
        last_suggestions = suggestions
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'total_suggestions': len(suggestions),
            'processed_products': len(data_df)
        })
        
    except Exception as e:
        return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500

@logistics_bp.route('/export', methods=['GET'])
@cross_origin()
def export_suggestions():
    global last_suggestions
    
    try:
        # Import pandas here to avoid deployment issues
        import pandas as pd
        
        if not last_suggestions:
            return jsonify({'error': 'Nenhuma sugestão disponível para exportar. Faça upload de uma planilha primeiro.'}), 400
        
        # Convert suggestions to DataFrame
        df = pd.DataFrame(last_suggestions)
        
        # Rename columns to Portuguese
        df = df.rename(columns={
            'produto_codigo': 'Código do Produto',
            'produto_descricao': 'Descrição do Produto',
            'loja_origem': 'Loja de Origem',
            'vendas_loja_origem': 'Vendas na Origem',
            'estoque_loja_origem': 'Estoque na Origem',
            'loja_destino_sugerida': 'Loja de Destino Sugerida',
            'vendas_loja_destino': 'Vendas no Destino',
            'quantidade_transferir': 'Quantidade a Transferir'
        })
        
        # Clean store names for better readability
        df['Loja de Origem'] = df['Loja de Origem'].str.replace('LJ ', '').str.replace(r'\d+', '', regex=True).str.strip()
        df['Loja de Destino Sugerida'] = df['Loja de Destino Sugerida'].str.replace('LJ ', '').str.replace(r'\d+', '', regex=True).str.strip()
        
        # Create Excel file in memory
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Write main suggestions sheet
            df.to_excel(writer, sheet_name='Sugestões de Transferência', index=False)
            
            # Create summary sheet
            summary_data = {
                'Métrica': [
                    'Total de Sugestões',
                    'Produtos Únicos',
                    'Lojas de Origem Envolvidas',
                    'Lojas de Destino Envolvidas',
                    'Data da Análise'
                ],
                'Valor': [
                    len(last_suggestions),
                    len(df['Código do Produto'].unique()),
                    len(df['Loja de Origem'].unique()),
                    len(df['Loja de Destino Sugerida'].unique()),
                    datetime.now().strftime('%d/%m/%Y %H:%M')
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Resumo', index=False)
            
            # Create summary by origin store
            origin_summary = df.groupby('Loja de Origem').agg({
                'Código do Produto': 'count',
                'Quantidade a Transferir': 'sum'
            }).rename(columns={
                'Código do Produto': 'Número de Produtos',
                'Quantidade a Transferir': 'Total de Itens'
            }).reset_index()
            origin_summary.to_excel(writer, sheet_name='Resumo por Loja Origem', index=False)
            
            # Create summary by destination store
            dest_summary = df.groupby('Loja de Destino Sugerida').agg({
                'Código do Produto': 'count',
                'Quantidade a Transferir': 'sum'
            }).rename(columns={
                'Código do Produto': 'Número de Produtos',
                'Quantidade a Transferir': 'Total de Itens'
            }).reset_index()
            dest_summary.to_excel(writer, sheet_name='Resumo por Loja Destino', index=False)
        
        output.seek(0)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'sugestoes_transferencia_{timestamp}.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': f'Erro ao exportar arquivo: {str(e)}'}), 500

def generate_transfer_suggestions(df):
    # Import pandas here to avoid deployment issues
    import pandas as pd
    
    stores = [
        "LJ 1Mega Loja",
        "LJ 2Mascote", 
        "LJ 3Tatuape",
        "LJ 4Indianopolis",
        "LJ 5Praia Grande",
        "LJ 6Fábrica",
        "LJ 10Osasco"
    ]
    
    transfer_suggestions = []
    
    for index, row in df.iterrows():
        try:
            product_code = row.iloc[0]  # First column is Código
            product_description = row.iloc[1]  # Second column is Descrição
            
            # Skip if product code or description is empty
            if pd.isna(product_code) or pd.isna(product_description):
                continue
            
            # Skip if it's a sub-group header
            if 'Sub-Grupo' in str(product_description):
                continue
            
            product_data = {"Código": product_code, "Descrição": product_description}
            
            # Extract sales and stock data for each store
            # Based on the model: columns are organized as store pairs (Vendas, Saldo)
            store_data_start_col = 6  # After Código, Descrição, Referência, Saldo Anterior, Total Recebimento, Total de Vendas, SaldoAtual
            
            for i, store in enumerate(stores):
                vendas_col_idx = store_data_start_col + (i * 2)  # Vendas column
                saldo_col_idx = store_data_start_col + (i * 2) + 1  # Saldo column
                
                # Handle missing columns gracefully
                sales = 0
                stock = 0
                
                if vendas_col_idx < len(row):
                    sales_val = row.iloc[vendas_col_idx]
                    if pd.notna(sales_val) and str(sales_val) != '-':
                        try:
                            sales = float(sales_val)
                        except (ValueError, TypeError):
                            sales = 0
                
                if saldo_col_idx < len(row):
                    stock_val = row.iloc[saldo_col_idx]
                    if pd.notna(stock_val) and str(stock_val) != '-':
                        try:
                            stock = float(stock_val)
                        except (ValueError, TypeError):
                            stock = 0
                
                product_data[f"{store}_Vendas"] = sales
                product_data[f"{store}_Saldo"] = stock
            
            # Analyze transfer opportunities
            for current_store in stores:
                current_store_sales = product_data.get(f"{current_store}_Vendas", 0)
                current_store_stock = product_data.get(f"{current_store}_Saldo", 0)
                
                # Condition: low sales (0) and positive stock
                if current_store_sales == 0 and current_store_stock > 0:
                    # Find store with highest sales for this product
                    max_sales = -1
                    destination_store = None
                    
                    for other_store in stores:
                        if other_store != current_store:
                            other_store_sales = product_data.get(f"{other_store}_Vendas", 0)
                            if other_store_sales > max_sales:
                                max_sales = other_store_sales
                                destination_store = other_store
                    
                    if destination_store and max_sales > 0:
                        transfer_suggestions.append({
                            "produto_codigo": str(product_code),
                            "produto_descricao": str(product_description),
                            "loja_origem": current_store,
                            "vendas_loja_origem": float(current_store_sales),
                            "estoque_loja_origem": float(current_store_stock),
                            "loja_destino_sugerida": destination_store,
                            "vendas_loja_destino": float(max_sales),
                            "quantidade_transferir": float(current_store_stock)
                        })
        
        except Exception as e:
            # Skip problematic rows and continue processing
            continue
    
    return transfer_suggestions

