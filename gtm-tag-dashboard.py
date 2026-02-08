import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from matplotlib.patches import Rectangle
import numpy as np

def load_tag_data(filename):
    """Load tag dependency data from JSON file"""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_tag_complexity_dashboard(data):
    """Create a comprehensive dashboard showing tag complexity and dependencies"""
    
    # Extract key metrics
    tags_data = []
    for tag in data:
        total_vars = sum(tag['all_variables'].values())
        unique_vars = len(tag['all_variables'])
        direct_vars = len(tag['direct_variables'])
        
        tags_data.append({
            'name': tag['name'],
            'type': tag['type'],
            'total_evaluations': total_vars,
            'unique_variables': unique_vars,
            'direct_variables': direct_vars,
            'avg_usage_per_var': total_vars / unique_vars if unique_vars > 0 else 0,
            'is_custom': tag['custom_template_info'] is not None
        })
    
    df = pd.DataFrame(tags_data)
    
    # Create figure with subplots
    fig = plt.figure(figsize=(20, 16))
    fig.suptitle('GTM Tag Dependency Analysis Dashboard', fontsize=20, fontweight='bold')
    
    # 1. Top 10 Most Complex Tags (by total evaluations)
    ax1 = plt.subplot(3, 3, 1)
    top_complex = df.nlargest(10, 'total_evaluations')
    bars1 = ax1.barh(range(len(top_complex)), top_complex['total_evaluations'])
    ax1.set_yticks(range(len(top_complex)))
    ax1.set_yticklabels([name[:30] + '...' if len(name) > 30 else name 
                         for name in top_complex['name']], fontsize=9)
    ax1.set_xlabel('Total Variable Evaluations')
    ax1.set_title('Top 10 Most Complex Tags\n(Total Variable Evaluations)', fontweight='bold')
    ax1.invert_yaxis()
    
    # Add value labels
    for i, (idx, row) in enumerate(top_complex.iterrows()):
        ax1.text(row['total_evaluations'] + 1, i, str(row['total_evaluations']), 
                va='center', fontsize=8)
    
    # 2. Unique Variables per Tag
    ax2 = plt.subplot(3, 3, 2)
    top_unique = df.nlargest(10, 'unique_variables')
    bars2 = ax2.barh(range(len(top_unique)), top_unique['unique_variables'])
    ax2.set_yticks(range(len(top_unique)))
    ax2.set_yticklabels([name[:30] + '...' if len(name) > 30 else name 
                         for name in top_unique['name']], fontsize=9)
    ax2.set_xlabel('Unique Variables Count')
    ax2.set_title('Top 10 Tags by Unique Variables', fontweight='bold')
    ax2.invert_yaxis()
    
    for i, (idx, row) in enumerate(top_unique.iterrows()):
        ax2.text(row['unique_variables'] + 0.5, i, str(row['unique_variables']), 
                va='center', fontsize=8)
    
    # 3. Tag Type Distribution
    ax3 = plt.subplot(3, 3, 3)
    type_counts = df['type'].value_counts()
    colors = plt.cm.Set3(range(len(type_counts)))
    wedges, texts, autotexts = ax3.pie(type_counts.values, labels=None, autopct='%1.1f%%',
                                       colors=colors, startangle=90)
    ax3.set_title('Tag Type Distribution', fontweight='bold')
    
    # Create legend with full names
    legend_labels = [f'{name[:25]}... ({count})' if len(name) > 25 else f'{name} ({count})' 
                     for name, count in type_counts.items()]
    ax3.legend(wedges, legend_labels, loc='center left', bbox_to_anchor=(1, 0, 0.5, 1),
              fontsize=8)
    
    # 4. Scatter plot: Unique vs Total Variables
    ax4 = plt.subplot(3, 3, 4)
    scatter = ax4.scatter(df['unique_variables'], df['total_evaluations'], 
                         s=100, alpha=0.6, c=df['is_custom'], cmap='viridis')
    ax4.set_xlabel('Unique Variables')
    ax4.set_ylabel('Total Evaluations')
    ax4.set_title('Variable Complexity Distribution', fontweight='bold')
    ax4.grid(True, alpha=0.3)
    
    # Add diagonal reference line
    max_val = max(df['unique_variables'].max(), df['total_evaluations'].max())
    ax4.plot([0, max_val], [0, max_val], 'r--', alpha=0.5, label='1:1 ratio')
    ax4.legend(['1:1 ratio', 'Standard Tag', 'Custom Template'], fontsize=8)
    
    # 5. Variable Reuse Efficiency
    ax5 = plt.subplot(3, 3, 5)
    top_reuse = df.nlargest(10, 'avg_usage_per_var')
    bars5 = ax5.barh(range(len(top_reuse)), top_reuse['avg_usage_per_var'])
    ax5.set_yticks(range(len(top_reuse)))
    ax5.set_yticklabels([name[:30] + '...' if len(name) > 30 else name 
                         for name in top_reuse['name']], fontsize=9)
    ax5.set_xlabel('Average Usage per Variable')
    ax5.set_title('Top 10 Tags - Variable Reuse Efficiency', fontweight='bold')
    ax5.invert_yaxis()
    
    for i, (idx, row) in enumerate(top_reuse.iterrows()):
        ax5.text(row['avg_usage_per_var'] + 0.02, i, f"{row['avg_usage_per_var']:.2f}", 
                va='center', fontsize=8)
    
    # 6. Custom vs Standard Tags Comparison
    ax6 = plt.subplot(3, 3, 6)
    custom_stats = df.groupby('is_custom').agg({
        'total_evaluations': 'mean',
        'unique_variables': 'mean',
        'direct_variables': 'mean'
    }).round(2)
    
    x = np.arange(3)
    width = 0.35
    
    bars1 = ax6.bar(x - width/2, custom_stats.loc[False], width, label='Standard Tags')
    bars2 = ax6.bar(x + width/2, custom_stats.loc[True], width, label='Custom Templates')
    
    ax6.set_xlabel('Metrics')
    ax6.set_ylabel('Average Count')
    ax6.set_title('Standard vs Custom Template Tags', fontweight='bold')
    ax6.set_xticks(x)
    ax6.set_xticklabels(['Total Evals', 'Unique Vars', 'Direct Vars'])
    ax6.legend()
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax6.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=8)
    
    # 7. Most Used Variables Across Tags
    ax7 = plt.subplot(3, 3, 7)
    all_vars = {}
    for tag in data:
        for var, count in tag['all_variables'].items():
            if var not in all_vars:
                all_vars[var] = {'total_usage': 0, 'tag_count': 0}
            all_vars[var]['total_usage'] += count
            all_vars[var]['tag_count'] += 1
    
    var_df = pd.DataFrame.from_dict(all_vars, orient='index')
    var_df['name'] = var_df.index
    top_vars = var_df.nlargest(10, 'tag_count')
    
    bars7 = ax7.barh(range(len(top_vars)), top_vars['tag_count'])
    ax7.set_yticks(range(len(top_vars)))
    ax7.set_yticklabels([name[:30] + '...' if len(name) > 30 else name 
                         for name in top_vars['name']], fontsize=9)
    ax7.set_xlabel('Number of Tags Using Variable')
    ax7.set_title('Most Common Variables Across Tags', fontweight='bold')
    ax7.invert_yaxis()
    
    for i, (idx, row) in enumerate(top_vars.iterrows()):
        ax7.text(row['tag_count'] + 0.5, i, f"{row['tag_count']} tags", 
                va='center', fontsize=8)
    
    # 8. Complexity Heatmap
    ax8 = plt.subplot(3, 3, 8)
    complexity_matrix = []
    tag_names = []
    
    # Select top 15 tags by total evaluations for heatmap
    top_tags = df.nlargest(15, 'total_evaluations')
    
    for _, tag in top_tags.iterrows():
        tag_names.append(tag['name'][:20] + '...' if len(tag['name']) > 20 else tag['name'])
        complexity_matrix.append([
            tag['total_evaluations'],
            tag['unique_variables'],
            tag['direct_variables'],
            tag['avg_usage_per_var'] * 10  # Scale for visibility
        ])
    
    im = ax8.imshow(complexity_matrix, cmap='YlOrRd', aspect='auto')
    ax8.set_xticks(range(4))
    ax8.set_xticklabels(['Total\nEvals', 'Unique\nVars', 'Direct\nVars', 'Avg Usage\n(x10)'], 
                        rotation=45, ha='right')
    ax8.set_yticks(range(len(tag_names)))
    ax8.set_yticklabels(tag_names, fontsize=8)
    ax8.set_title('Tag Complexity Heatmap\n(Top 15 Complex Tags)', fontweight='bold')
    
    # Add text annotations
    for i in range(len(tag_names)):
        for j in range(4):
            text = ax8.text(j, i, f'{complexity_matrix[i][j]:.0f}',
                           ha="center", va="center", color="black", fontsize=7)
    
    # 9. Summary Statistics
    ax9 = plt.subplot(3, 3, 9)
    ax9.axis('off')
    
    summary_text = f"""Summary Statistics:
    
Total Tags Analyzed: {len(df)}
Total Unique Variables: {len(all_vars)}

Average per Tag:
  • Total Evaluations: {df['total_evaluations'].mean():.1f}
  • Unique Variables: {df['unique_variables'].mean():.1f}
  • Direct Variables: {df['direct_variables'].mean():.1f}
  
Most Complex Tag:
  {df.loc[df['total_evaluations'].idxmax(), 'name'][:40]}
  ({df['total_evaluations'].max()} evaluations)

Most Efficient Tag:
  {df.loc[df['avg_usage_per_var'].idxmin(), 'name'][:40]}
  ({df['avg_usage_per_var'].min():.2f} avg usage/var)

Custom Templates: {df['is_custom'].sum()} / {len(df)}
"""
    
    ax9.text(0.05, 0.95, summary_text, transform=ax9.transAxes, 
             fontsize=11, verticalalignment='top', 
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    return fig, df

def save_detailed_report(df, all_vars, filename='tag_complexity_report.txt'):
    """Save a detailed text report of the analysis"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("GTM TAG COMPLEXITY ANALYSIS REPORT\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("EXECUTIVE SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total Tags Analyzed: {len(df)}\n")
        f.write(f"Total Unique Variables: {len(all_vars)}\n")
        f.write(f"Average Variables per Tag: {df['unique_variables'].mean():.1f}\n")
        f.write(f"Average Total Evaluations per Tag: {df['total_evaluations'].mean():.1f}\n\n")
        
        f.write("TOP 10 MOST COMPLEX TAGS (by total evaluations)\n")
        f.write("-" * 40 + "\n")
        for idx, row in df.nlargest(10, 'total_evaluations').iterrows():
            f.write(f"{row['name']}\n")
            f.write(f"  Type: {row['type']}\n")
            f.write(f"  Total Evaluations: {row['total_evaluations']}\n")
            f.write(f"  Unique Variables: {row['unique_variables']}\n")
            f.write(f"  Average Usage per Variable: {row['avg_usage_per_var']:.2f}\n\n")
        
        f.write("\nMOST COMMONLY USED VARIABLES\n")
        f.write("-" * 40 + "\n")
        var_df = pd.DataFrame.from_dict(all_vars, orient='index')
        var_df['name'] = var_df.index
        for idx, row in var_df.nlargest(15, 'tag_count').iterrows():
            f.write(f"{row['name']}\n")
            f.write(f"  Used in {row['tag_count']} tags\n")
            f.write(f"  Total usage count: {row['total_usage']}\n\n")

# Main execution
if __name__ == "__main__":
    # Load the data
    data = load_tag_data('output.json')
    
    # Create dashboard
    fig, df = create_tag_complexity_dashboard(data)
    
    # Save the dashboard
    plt.savefig('gtm_tag_complexity_dashboard.png', dpi=300, bbox_inches='tight')
    print("Dashboard saved as 'gtm_tag_complexity_dashboard.png'")
    
    # Extract all variables data for report
    all_vars = {}
    for tag in data:
        for var, count in tag['all_variables'].items():
            if var not in all_vars:
                all_vars[var] = {'total_usage': 0, 'tag_count': 0}
            all_vars[var]['total_usage'] += count
            all_vars[var]['tag_count'] += 1
    
    # Save detailed report
    save_detailed_report(df, all_vars)
    print("Detailed report saved as 'tag_complexity_report.txt'")
    
    # Show the dashboard
    plt.show()
